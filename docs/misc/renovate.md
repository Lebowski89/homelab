## Updating Container Images

This project uses Renovate to monitor and create pull requests for container image updates used by Docker and Podman services, in addition to other dependencies.

This is achieved by:

1) Pinning each image tag to a version number where possible
2) Pinning to digests for images that only use tags, such as `lastest` and `master`
3) Using simple tags for ease of compatibility (i.e, 1.4.5, v1.4.5)
4) Using regex to help renovate read more exotic tags (i.e, `v3-3.3.1-release.579`)
5) Set Renovate to scan all yaml files for tags, since I don't store templated compose files

I really enjoy this method updating. Renovate creates PRs with the tag update, I then read the change notes to see if any changes are required on my end before merging. It voids potential issues of automatic updates (I ran Watchtower extensively in the past), while not requiring a separate Diun container. I also like that it only changes the image tag and leaves me in control of when I redeploy the service.

Minor, patch and digest updates for non-critical images join the nightly batch,
scheduled from 03:00 to 07:59 Australia/Melbourne, with at least two updates required.
The group is called `nightly non-critical container image updates`; its existing
`weekly-docker-minor-patch` branch slug is retained to preserve open branches.
Image updates use the `container image updates` label. Renovate's technical
datasource remains `docker` for both runtimes.
Same-tag digest changes for already pinned images, including Autobrr and Seerr,
qualify for this batch. This does not enable digest pinning for additional images
or change any service image reference.

The existing critical classification is unchanged: PostgreSQL, Valkey, Traefik,
Authelia, Infisical, NetBox, Plex, Prometheus, Alertmanager, Grafana, Loki, Alloy,
and HAProxy receive separate updates. The batch exclusions and critical rule
match the same image identities, including shorthand and `docker.io/` names;
official images also accept the `library/` namespace. Traefik's special branch
names use the same aliases. Other registries and similarly named images are not
implicitly classified as critical.

Image automerge stays disabled. Major updates still require Dependency Dashboard
approval. Version restrictions (including Forgejo's 15.0.x rootless LTS line),
tag-plus-digest extraction and digest pinning policy are unchanged.

The global minimum release age remains **three days**. Renovate's container-image
datasource [documents release timestamp support only for Docker Hub](https://docs.renovatebot.com/modules/datasource/docker/).
Images whose names begin with the complete `ghcr.io/`, `lscr.io/` or
`codeberg.org/` registry prefix therefore use `minimumReleaseAgeBehaviour:
"timestamp-optional"`. This includes service images and bootstrap defaults, such
as NetBox on LSCR and Hugo on GHCR. The exception applies only to the `docker`
datasource. Docker Hub, including shorthand, `library/` and `docker.io/` names,
other registries, and non-container dependencies retain the default
`timestamp-required` behaviour.

When a timestamp is missing, `timestamp-optional` **bypasses age verification**;
it does **not** implement an equivalent three-day waiting period, including a
wait since first discovery. When a timestamp is available, it must still satisfy
the configured three-day age. See [Renovate's release-age behaviour](https://docs.renovatebot.com/configuration-options/#minimumreleaseagebehaviour).

After these changes reach `main`, let Renovate refresh the Dependency Dashboard
and regenerate the existing nightly batch. To request regeneration, select the
nightly PR's **rebase/retry** checkbox or the corresponding action in the
Dependency Dashboard. Separate Autobrr/Seerr digest entries should join the batch
instead of remaining separate, and missing timestamps from the three allowed
registries should stop holding updates pending indefinitely. Scheduling, the
minimum group size of two, major approval and other update policies still apply;
available timestamps can still leave updates waiting for three days. Review the
refreshed dashboard and regenerated diff before merging. See [Renovate's rebasing documentation](https://docs.renovatebot.com/updating-rebasing/).

Focused local regression checks run with:

```sh
/opt/ansible/ansible-venv/bin/python -m pytest -q tests/unit/test_renovate_container_images.py
```

These checks execute the configured extraction regex and package-name,
datasource and update-type selectors with Node.js against aliases, real service
files, effective base-plus-target images, and bootstrap defaults. They cover
tag-plus-digest references, same-tag digest batching, major approval, disabled
image automerge, and registry timestamp exceptions with non-container controls.
They do not run Renovate, resolve presets, fetch releases, calculate release age,
or prove hosted dashboard/branch/PR behaviour. When Renovate tooling is available, also
run its configuration validator and an extraction-only local dry run before
relying on the hosted result; do not install dependencies just for these checks.
