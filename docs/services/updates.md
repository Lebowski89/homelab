## Updating Docker Images

This project uses renovate (repo bot) to monitor and create pull requests for updates to Docker services I use (in addition other dependencies). 

This is achieved by:

1) Pinning each image tag to a version number where possible
2) Pinning to digests for images that only use tags, such as `lastest` and `master`
3) Using simple tags for ease of compatibility (i.e, 1.4.5, v1.4.5)
4) Using regex to help renovate read more exotic tags (i.e, `v3-3.3.1-release.579`)
5) Set Renovate to scan all yaml files for tags, since I don't store templated compose files

I really enjoy this method updating. Renovate creates PRs with the tag update, I then read the change notes to see if any changes are required on my end before merging. It voids potential issues of automatic updates (I ran Watchtower extensively in the past), while not requiring a separate Diun container. I also like that it only changes the image tag and leaves me in control of when I redeploy the service.
