"""Scoped policy union transactions for service operations.

The reservation lives in the existing policy, not in an acceptance registry.
It prevents two operations on one service from crossing their stop/start windows.
Every transaction rereads the latest union while holding the helper writer lock.
"""

import hashlib
import json
from copy import deepcopy


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def endpoint_key(endpoint):
    return endpoint["port"]


def merge(current, request, phase, token, baseline_ports=None):
    """Pure union planning. Never restore a previously read whole-policy snapshot."""
    require(phase in {"stage", "prepare_remove", "finish", "remove"}, "unsupported lifecycle phase")
    profile, service = request["profile"], request["service"]
    policy = deepcopy(current)
    records = policy.setdefault("managed_services", {})
    saved = records.get(service, {})
    if saved.get("runtime"):
        require(
            saved["runtime"]["hosts"] == request["runtime"]["hosts"] and saved["runtime"]["binding"] == request["runtime"]["binding"],
            "provider placement/runtime identity changed; use a reviewed ownership/placement transition before ordinary maintenance",
        )
    contract = fingerprint({k: v for k, v in request.items() if k != "source_addresses"})
    if phase in {"stage", "prepare_remove"}:
        require(
            not saved.get("pending")
            or saved.get("token") == token
            or (
                request.get("action") == "remove"
                and saved.get("declaration") == fingerprint({k: v for k, v in request.items() if k not in {"action", "source_addresses"}})
            ),
            "service has an unfinished operation; inspect its runtime and retry with the recorded operation token",
        )
    else:
        require(
            saved.get("token") == token and saved.get("contract") == contract, "service operation no longer matches its staged declaration"
        )
    if phase == "prepare_remove":
        # Reserve only installed ownership. Removal must never create endpoint
        # guards, accounts or persistence merely to inspect an absent writer.
        owned = saved.get("ports")
        if owned is None:
            owned = (
                [e["port"] for e in policy["endpoints"] if e["service"] == request["runtime"]["service"]]
                if profile == "mgt"
                else sorted(set(baseline_ports or []) & set(policy["ports"]))
            )
        records[service] = {
            **saved,
            "contract": contract,
            "token": token,
            "pending": True,
            "removing": True,
            "declaration": fingerprint({k: v for k, v in request.items() if k not in {"action", "source_addresses"}}),
            "ports": sorted(owned),
            "staged_ports": saved.get("staged_ports", []),
            "runtime": deepcopy(request["runtime"]),
        }
        return policy
    desired = deepcopy(request["endpoints"])
    if profile == "mgt":
        previous = [e for e in policy["endpoints"] if e["service"] == request["runtime"]["service"]]
        # Exact runtime names are unique on this host. Previously manual entries
        # are adopted only for this provider, preserving their legacy IDs.
        owned = sorted(set(saved.get("ports", [e["port"] for e in previous])) | set(saved.get("staged_ports", [])))
        if phase == "stage":
            for endpoint in desired:
                matches = [e for e in policy["endpoints"] if e["port"] == endpoint["port"]]
                require(len(matches) <= 1, "duplicate installed publication")
                if matches:
                    old = matches[0]
                    require(old["service"] == endpoint["service"], "publication is owned by another service")
                    old["callers"] = sorted(set(old["callers"]) | set(endpoint["callers"]))
                    old["ids"] = sorted(set(old["ids"]) | set(endpoint["ids"]))
                else:
                    policy["endpoints"].append(endpoint)
            updates = deepcopy(request["callers"])
            selected_record = request["runtime"]
            if selected_record["hosts"] == [request["host"]] and selected_record.get("network_mode") != "host":
                for name in {service, selected_record["service"]} & policy["callers"].keys():
                    updates[name] = selected_record
            for name, record in updates.items():
                binding = record["binding"]
                if binding is None:
                    require(bool(policy["callers"].get(name)), "legacy native/remote caller has no verified installed binding: " + name)
                    continue
                bindings = policy["callers"].setdefault(name, [])
                # Preserve accepted and rollback bindings. Add only the exact
                # canonical runtime identity, never a shared subnet or root UID.
                if binding not in bindings:
                    bindings.append(deepcopy(binding))
            record = request["runtime"]
            principal = policy.setdefault("principals", {}).setdefault(record["service"], {})
            principal.update(
                inventory_hosts=request["host"],
                future_runtime=record["binding"]["runtime"],
                future_account=record["binding"].get("account"),
            )
        else:
            keep = [e for e in policy["endpoints"] if e["port"] not in owned + saved.get("staged_ports", [])]
            if phase == "finish":
                for endpoint in desired:
                    old = next((e for e in previous if e["port"] == endpoint["port"]), None)
                    if old:
                        endpoint["ids"] = sorted(set(old["ids"]) | set(endpoint["ids"]))
                    keep.append(endpoint)
            policy["endpoints"] = keep
            referenced = {name for e in keep for name in e["callers"]}
            # Only mechanically added bindings are eligible for pruning. Never
            # discard retained acceptance, operator or rollback evidence.
            for name in list(policy["callers"]):
                if name not in referenced:
                    policy["callers"][name] = [b for b in policy["callers"][name] if b.get("kind") != "service"]
                    if not policy["callers"][name]:
                        del policy["callers"][name]
        policy["endpoints"].sort(key=endpoint_key)
    else:
        require(policy.get("sources_verified") is True, "worker source path has not been verified")
        require(
            request.get("sources") is None or set(policy["sources"]) == set(request["sources"]),
            "worker source declaration changed; verify the actual caller source before applying protection",
        )
        ports = set(policy["ports"])
        owned = sorted(set(saved.get("ports", [])) | set(saved.get("staged_ports", [])))
        # Existing manual worker ports have no provider ownership. Adopt only
        # the desired ports; never infer ownership of other accepted entries.
        if not saved:
            owned = sorted(set(baseline_ports or []) & ports)
        if phase == "stage":
            for name, record in records.items():
                if name != service:
                    require(
                        not set(e["port"] for e in desired) & set(record.get("staged_ports", record.get("ports", []))),
                        "worker publication is owned by another service",
                    )
            ports.update(e["port"] for e in desired)
        else:
            ports.difference_update(owned + saved.get("staged_ports", []))
            if phase == "finish":
                ports.update(e["port"] for e in desired)
        policy["ports"] = sorted(ports)
    policy["lifecycle"] = True
    if phase == "remove":
        records[service] = {
            "contract": contract,
            "token": token,
            "pending": True,
            "removing": True,
            "declaration": fingerprint({k: v for k, v in request.items() if k not in {"action", "source_addresses"}}),
            "ports": owned,
            "staged_ports": saved.get("staged_ports", []),
            "runtime": deepcopy(request["runtime"]),
        }
    else:
        records[service] = {
            "contract": contract,
            "declaration": fingerprint({k: v for k, v in request.items() if k not in {"action", "source_addresses"}}),
            "token": token,
            "pending": phase == "stage",
            "ports": owned if phase == "stage" else sorted(e["port"] for e in desired),
            "staged_ports": sorted(e["port"] for e in desired),
            "runtime": deepcopy(request["runtime"]),
        }
    return policy


def transact(store, request, phase, token, runtime):
    """All current-state validation and policy writes share the reconciler lock.

    store methods implement the existing profile's kernel and persistence
    contract. A failed apply deliberately leaves staged protection and its
    reservation for scoped recovery; no stale snapshot is written back.
    """
    with store.lock():
        current = store.read()
        store.validate(current)
        require(
            current["inventory_host"] == request["host"] and current["inventory_address"] == request["address"],
            "installed policy belongs to a different inventory host/address",
        )
        if phase == "activate":
            saved = current.get("managed_services", {}).get(request["service"], {})
            require(saved.get("token") == token, "activation does not belong to this operation")
            store.test(current, request, "activate")
            return store.apply(current, request, "stage") or {"changed": False, "families": [4, 6]}
        if phase == "cancel":
            saved = current.get("managed_services", {}).get(request["service"], {})
            require(saved.get("token") == token, "cannot cancel another operation's reservation")
            saved.update(pending=False, failed=True, failed_stage=True)
            store.write(current)
            return {"changed": False, "families": [4, 6], "protection_retained": True}
        if phase == "abort":
            saved = current.get("managed_services", {}).get(request["service"], {})
            require(saved.get("token") == token, "cannot release another operation's reservation")
            runtime("absent")
            current["managed_services"][request["service"]].update(pending=False, failed=True)
            store.test(current, request, "abort")
            store.write(current)
            store.apply(current, request, "stage")
            return {"changed": False, "families": [4, 6], "protection_retained": True}
        # Reject a competing reservation before inspecting a potentially
        # half-applied stage. Only its own exact operation may resume that stage.
        baseline = runtime("dependencies") if phase in {"stage", "prepare_remove"} else {}
        candidate = merge(current, request, phase, token, (baseline or {}).get("baseline_ports", []))
        if phase == "prepare_remove":
            saved = current.get("managed_services", {}).get(request["service"], {})
            store.audit(current, recovering=bool(saved.get("removing")))
            store.write(candidate)
            return {"changed": False, "families": [4, 6], "protection_retained": True}
        if phase == "stage":
            saved = current.get("managed_services", {}).get(request["service"], {})
            store.audit(current, recovering=saved.get("pending") and (saved.get("token") == token or request.get("action") == "remove"))
        elif phase == "remove":
            runtime("absent")
            saved = current.get("managed_services", {}).get(request["service"], {})
            retired = sorted(set(saved.get("ports", []) + saved.get("staged_ports", [])))
            if retired:
                runtime(("obsolete_absent", retired))
        elif phase == "finish":
            runtime("healthy")
            saved = current.get("managed_services", {}).get(request["service"], {})
            obsolete = sorted(
                set(saved.get("ports", []))
                - {p[0] for p in request["runtime"].get("all_publications", request["runtime"].get("publications", [])) if p[2] == "tcp"}
            )
            if obsolete:
                runtime(("obsolete_absent", obsolete))
        store.validate(candidate)
        # Both families are tested before any file or kernel writes.
        store.test(candidate, request, phase)
        if phase != "remove" and candidate == current and not (phase == "stage" and saved.get("pending")):
            store.audit(current)
            return {"changed": False, "families": [4, 6]}
        try:
            store.prepare(candidate)
            store.write(candidate)
            applied = store.apply(candidate, request, phase) or {}
        except (OSError, ValueError, RuntimeError):
            # A stage error is returned before the adapter can start/change a
            # writer. Release only this reservation, retaining every deny guard
            # and reading the latest union again rather than restoring a snapshot.
            if phase == "stage":
                try:
                    retained = store.read()
                    saved = retained.get("managed_services", {}).get(request["service"], {})
                    if saved.get("token") == token:
                        saved.update(pending=False, failed=True, failed_stage=True)
                        store.write(retained)
                except (OSError, ValueError, RuntimeError):
                    pass  # Keep the original error; an incomplete reservation remains visible.
            raise
        if phase != "stage":
            store.audit(candidate)
        if phase == "remove":
            referenced = any(request["runtime"]["service"] in e.get("callers", []) for e in candidate.get("endpoints", []))
            if referenced:
                # Keep the exact logical client's retirement proof while its
                # bindings remain referenced. Missing identities produce no
                # allow rules; reappearing identities must resolve normally.
                candidate["managed_services"][request["service"]].update(
                    pending=False, removing=False, removed=True, ports=[], staged_ports=[]
                )
            else:
                candidate["managed_services"].pop(request["service"], None)
            store.write(candidate)
        return {
            "changed": {k: v for k, v in candidate.items() if k != "managed_services"}
            != {k: v for k, v in current.items() if k != "managed_services"}
            or applied.get("changed", False),
            "families": [4, 6],
        }


def install_union(current, proposed, profile):
    """Administrative installation may extend/repair, never drop live ownership.

    It cannot overwrite declaration-backed endpoints or an in-flight service
    operation. Ordinary service changes must use their adapter lifecycle.
    """
    require(
        current["inventory_host"] == proposed["inventory_host"]
        and current["inventory_address"] == proposed["inventory_address"]
        and current["backend"] == proposed["backend"],
        "installed policy inventory/backend differs",
    )
    require(
        not any(v.get("pending") for v in current.get("managed_services", {}).values()),
        "a service operation is unfinished; do not overwrite its policy",
    )
    result = deepcopy(current)
    if profile == "mgt":
        for endpoint in proposed["endpoints"]:
            matches = [e for e in result["endpoints"] if e["port"] == endpoint["port"]]
            if matches:
                require(matches == [endpoint], "existing endpoint differs; use its normal service operation to reconcile it")
            else:
                result["endpoints"].append(deepcopy(endpoint))
        for name, bindings in proposed["callers"].items():
            for binding in bindings:
                target = result["callers"].setdefault(name, [])
                if binding not in target:
                    target.append(deepcopy(binding))
        for name, principal in proposed.get("principals", {}).items():
            require(
                name not in result.get("principals", {}) or result["principals"][name] == principal,
                "installed caller/provider declaration differs; reconcile through the service lifecycle",
            )
            result.setdefault("principals", {})[name] = deepcopy(principal)
        result["endpoints"].sort(key=endpoint_key)
    else:
        require(set(result["sources"]) == set(proposed["sources"]), "worker source changes require explicit source re-verification")
        result["ports"] = sorted(set(result["ports"]) | set(proposed["ports"]))
    return result


def future_caller(policy, name):
    """A new declaration can authorise an absent client without inventing its PID.

    Once its service has been managed, or a legacy accepted binding exists,
    disappearance is an error rather than a fresh-client bootstrap exception.
    """
    if any(value.get("runtime", {}).get("service") == name for value in policy.get("managed_services", {}).values()):
        return False
    bindings = policy.get("callers", {}).get(name, [])
    return bool(bindings) and all(binding.get("kind") == "service" for binding in bindings)


def deferred_caller(policy, message):
    name, _, reason = message.partition(": ")
    return reason.startswith(("no local running caller for docker:", "no local running caller for podman:")) and future_caller(policy, name)
