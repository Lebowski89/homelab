## Updating Docker Images

This project uses the renovate (repo) bot to monitor and to create pull requests for updates to Docker apps/services I use (in addition to python and other dependencies). For this reason, when and where possible each Docker image is pinned to a version number. This repo does not store templated compose files, so the renovate.json is configured to read my service yml files:

```
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",

  "extends": ["config:recommended"],

  "timezone": "Australia/Melbourne",
  "dependencyDashboard": true,

  "labels": ["renovate"],
  "prConcurrentLimit": 5,
  "prHourlyLimit": 2,

  "rangeStrategy": "pin",

  "semanticCommits": "enabled",
  "semanticCommitType": "chore",
  "semanticCommitScope": "deps",

  "commitBodyTable": true,

  "prBodyNotes": [
    "Homelab note: review upstream release notes/changelog before merging."
  ],

  "customManagers": [
    {
      "customType": "regex",
      "managerFilePatterns": ["/\\.ya?ml$/"],
      "matchStrings": [
        "image:\\s*[\"']?(?<depName>[^\"'\\s:@]+(?:\\/[^\"'\\s:@]+)*)\\s*:\\s*(?<currentValue>[^\"'\\s@]+)(?:@(?<currentDigest>sha256:[a-f0-9]+))?[\"']?"
      ],
      "datasourceTemplate": "docker"
    }
  ],

  "packageRules": [
    {
      "matchDatasources": ["docker"],
      "groupName": null,
      "automerge": false
    },
    {
      "matchDatasources": ["docker"],
      "matchUpdateTypes": ["major"],
      "labels": ["renovate", "major"],
      "prPriority": 10
    },
    {
      "matchDatasources": ["docker"],
      "matchUpdateTypes": ["minor"],
      "labels": ["renovate", "minor"],
      "prPriority": 0
    },
    {
      "matchDatasources": ["docker"],
      "matchUpdateTypes": ["patch"],
      "labels": ["renovate", "patch"],
      "prPriority": -1
    }
  ]
}
```

I am really enjoying this method of updating. In the past I have tried it all, which has been quite the learning experience. And while I don't have the horror stories some seem to have with things such as automatic updates (and I ran Watchtower for quite some time), I find that I am better equipped to keep up and maintain large numbers of concurrent services if I'm able to control when updates occur. It just gives me the time to read changelogs and make the changes required to keep up with ever-evolving apps.