## Updating Container Images

This project uses Renovate to monitor and create pull requests for container image updates used by Docker and Podman services, in addition to other dependencies.

This is achieved by:

1) Pinning each image tag to a version number where possible
2) Pinning to digests for images that only use tags, such as `lastest` and `master`
3) Using simple tags for ease of compatibility (i.e, 1.4.5, v1.4.5)
4) Using regex to help renovate read more exotic tags (i.e, `v3-3.3.1-release.579`)
5) Set Renovate to scan all yaml files for tags, since I don't store templated compose files

I really enjoy this method updating. Renovate creates PRs with the tag update, I then read the change notes to see if any changes are required on my end before merging. It voids potential issues of automatic updates (I ran Watchtower extensively in the past), while not requiring a separate Diun container. I also like that it only changes the image tag and leaves me in control of when I redeploy the service.

Minor and patch updates for non-critical images join the nightly batch, scheduled
from 03:00 to 07:59 Australia/Melbourne, with at least two updates required.
The group is called `nightly non-critical container image updates`; its existing
`weekly-docker-minor-patch` branch slug is retained to preserve open branches.
Image updates use the `container image updates` label. Renovate's technical
datasource remains `docker` for both runtimes.

The existing critical classification is unchanged: PostgreSQL, Valkey, Traefik,
Authelia, Infisical, NetBox, Plex, Prometheus, Alertmanager, Grafana, Loki, Alloy,
and HAProxy receive separate updates. The batch exclusions and critical rule
match the same image identities, including shorthand and `docker.io/` names;
official images also accept the `library/` namespace. Traefik's special branch
names use the same aliases. Other registries and similarly named images are not
implicitly classified as critical.

Image automerge stays disabled. Major updates still require Dependency Dashboard
approval. Version restrictions (including Forgejo's 15.0.x rootless LTS line),
release-age settings, tag-plus-digest extraction and digest handling are unchanged.

After this configuration reaches `main`, request Renovate to regenerate #672 by
selecting its **rebase/retry** checkbox, or its corresponding rebase action in
the Dependency Dashboard. Grafana and Alloy should then leave the non-critical
batch and receive separate critical updates, subject to the existing update
policies. The remaining batch can retain its branch; if fewer than two updates
remain, the minimum group size may defer it. Review the regenerated diff before
merging. See [Renovate's rebasing documentation](https://docs.renovatebot.com/updating-rebasing/).

Focused local regression checks run with:

```sh
/opt/ansible/ansible-venv/bin/python -m pytest -q tests/unit/test_renovate_container_images.py
```

These checks execute the configured extraction regex and package-name selectors
with Node.js against aliases, real service files, effective base-plus-target
images, and bootstrap defaults. They cover tag-plus-digest references and
non-critical controls. They do not run Renovate, resolve presets, fetch releases,
or prove hosted branch/PR behaviour. When Renovate tooling is available, also
run its configuration validator and an extraction-only local dry run before
relying on the hosted result; do not install dependencies just for these checks.
