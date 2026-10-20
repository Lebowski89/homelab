"""Patch only existing Alertmanager client routes; preserve other configuration."""

import ipaddress
import json
import re
from copy import deepcopy

import yaml
from ansible.errors import AnsibleFilterError


def _configuration(text):
    try:
        # Duplicate keys make both scope and preservation ambiguous.
        for node in yaml.compose_all(text):

            def unique(current):
                if isinstance(current, yaml.MappingNode):
                    keys = [key.value for key, _ in current.value]
                    if len(keys) != len(set(keys)):
                        raise ValueError
                    for _, value in current.value:
                        unique(value)
                elif isinstance(current, yaml.SequenceNode):
                    for value in current.value:
                        unique(value)

            unique(node)
        result = yaml.safe_load(text)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (yaml.YAMLError, ValueError, TypeError, RecursionError):
        raise AnsibleFilterError("managed configuration must be one unambiguous YAML mapping; source withheld") from None


def _route(record, target):
    if not isinstance(record, dict) or record.get("scheme", "http") not in {"http", "https"}:
        raise ValueError
    groups = record.get("static_configs")
    if not isinstance(groups, list) or len(groups) != 1 or groups[0].get("targets") not in [["alertmanager:9093"], [target]]:
        raise ValueError
    if record.get("relabel_configs") or any(key.endswith("_sd_configs") for key in record):
        raise ValueError
    desired = deepcopy(record)
    desired["scheme"] = "https"
    desired["static_configs"][0]["targets"] = [target]
    return desired


def docker_services_prometheus_alertmanager_routes(text, discovery, scrape):
    before = _configuration(text)
    try:
        target = discovery["alertmanagers"][0]["static_configs"][0]["targets"][0]
        if not isinstance(target, str):
            raise ValueError
        # Ansible's tagged str subclass is not representable by PyYAML.
        target = str(target)
        if (
            discovery["alertmanagers"][0]["scheme"] != "https"
            or scrape["scheme"] != "https"
            or scrape["static_configs"][0]["targets"] != [target]
        ):
            raise ValueError
        desired = deepcopy(before)
        managers = before["alerting"]["alertmanagers"]
        jobs = before["scrape_configs"]
        selected = [index for index, job in enumerate(jobs) if job.get("job_name") == "alertmanager"]
        if len(managers) != 1 or len(selected) != 1:
            raise ValueError
        desired["alerting"]["alertmanagers"] = [_route(managers[0], target)]
        desired["scrape_configs"][selected[0]] = _route(jobs[selected[0]], target)
        patterns = [r"(?ms)^alerting:\n.*?(?=^\S|\Z)", r'(?ms)^  - job_name: (?:"alertmanager"|alertmanager)\n.*?(?=^  - job_name:|\Z)']
        if any(len(re.findall(pattern, text)) != 1 for pattern in patterns):
            raise ValueError
        if desired == before:
            return text
        candidate = re.sub(patterns[0], lambda _: yaml.safe_dump({"alerting": desired["alerting"]}, sort_keys=False, indent=2) + "\n", text)
        job = yaml.safe_dump([desired["scrape_configs"][selected[0]]], sort_keys=False, indent=2)
        candidate = re.sub(patterns[1], lambda _: "\n".join("  " + line if line else "" for line in job.splitlines()) + "\n\n", candidate)
        if _configuration(candidate) != desired:
            raise ValueError
        return candidate
    except (KeyError, IndexError, TypeError, AttributeError, ValueError):
        raise AnsibleFilterError(
            "require one managed Alertmanager discovery and scrape with the old alias or canonical target; source withheld"
        ) from None


def docker_services_loki_alertmanager_route(text, canonical):
    before = _configuration(text)
    try:
        target = str(_configuration(canonical)["ruler"]["alertmanager_url"])
        if not target.startswith("https://") or any(c in target for c in "\n\r\"'"):
            raise ValueError
        old = before["ruler"]["alertmanager_url"]
        if old not in {"http://alertmanager:9093", target}:
            raise ValueError
        if old == target:
            return text
        desired = deepcopy(before)
        desired["ruler"]["alertmanager_url"] = target
        blocks = list(re.finditer(r"(?ms)^ruler:\n.*?(?=^\S|\Z)", text))
        if len(blocks) != 1:
            raise ValueError
        block = blocks[0]
        replacement, count = re.subn(r"(?m)^  alertmanager_url:.*$", "  alertmanager_url: " + target, block.group())
        candidate = text[: block.start()] + replacement + text[block.end() :]
        if count != 1 or _configuration(candidate) != desired:
            raise ValueError
        return candidate
    except (KeyError, TypeError, ValueError):
        raise AnsibleFilterError(
            "require the single managed Loki ruler URL with old alias or canonical HTTPS destination; source withheld"
        ) from None


def docker_services_prometheus_scraparr_job(text, job):
    """Add/update only the bounded Scraparr job; preserve other loaded jobs."""
    before = _configuration(text)
    try:
        job = json.loads(json.dumps(job))
        target = job["static_configs"][0]["targets"][0]
        address, port = target.rsplit(":", 1)
        if (
            job["job_name"] != "scraparr"
            or not isinstance(target, str)
            or ipaddress.ip_address(address).version != 4
            or port != "17100"
            or job.get("scheme", "http") != "http"
            or job.get("metrics_path", "/metrics") != "/metrics"
            or job["static_configs"] != [{"targets": [target]}]
        ):
            raise ValueError
        desired = deepcopy(before)
        jobs = desired["scrape_configs"]
        selected = [i for i, record in enumerate(jobs) if record.get("job_name") == "scraparr"]
        if len(selected) > 1 or not isinstance(jobs, list):
            raise ValueError
        pattern = r'(?ms)^  - job_name: (?:"scraparr"|scraparr)\n.*?(?=^  - job_name:|^\S|\Z)'
        if selected:
            current = jobs[selected[0]]
            if (
                current.get("scheme", "http") != "http"
                or current.get("metrics_path", "/metrics") != "/metrics"
                or current.get("relabel_configs")
                or any(key.endswith("_sd_configs") for key in current)
                or current.get("static_configs") not in [[{"targets": ["scraparr:7100"]}], [{"targets": [target]}]]
                or len(re.findall(pattern, text)) != 1
            ):
                raise ValueError
            current["static_configs"] = [{"targets": [target]}]
            replacement = yaml.safe_dump([current], sort_keys=False, indent=2)
            body = "\n".join("  " + line if line else "" for line in replacement.splitlines()) + "\n\n"
            candidate = re.sub(pattern, lambda _: body, text)
        else:
            # Insert at the managed block start; never assume scrape_configs is
            # the last top-level mapping or append into an unrelated section.
            if len(re.findall(r"(?m)^scrape_configs:\s*$", text)) != 1:
                raise ValueError
            jobs.insert(0, job)
            replacement = yaml.safe_dump([job], sort_keys=False, indent=2)
            body = "\n".join("  " + line if line else "" for line in replacement.splitlines()) + "\n\n"
            candidate = re.sub(r"(?m)^scrape_configs:\s*$", lambda _: "scrape_configs:\n" + body, text, count=1)
        if desired == before:
            return text
        if _configuration(candidate) != desired:
            raise ValueError
        return candidate
    except (KeyError, IndexError, TypeError, AttributeError, ValueError, yaml.YAMLError):
        raise AnsibleFilterError("require absent or single managed Scraparr job with old alias/canonical target; source withheld") from None


class FilterModule:
    def filters(self):
        return {
            "docker_services_prometheus_alertmanager_routes": docker_services_prometheus_alertmanager_routes,
            "docker_services_loki_alertmanager_route": docker_services_loki_alertmanager_route,
            "docker_services_prometheus_scraparr_job": docker_services_prometheus_scraparr_job,
        }
