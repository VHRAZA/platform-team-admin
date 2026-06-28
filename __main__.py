"""A Python Pulumi program"""

import pulumi
import pulumi_github as github

platform_team_admin = github.Repository(
    "platform-team-admin",
    name="platform-team-admin",
    description="Repository to manage platform team membership and admin artifacts",
    visibility="private",
    opts=pulumi.ResourceOptions(protect=True),
)

platform_core = github.Repository(
    "platform-core",
    name="platform-core",
    description="Core platform runtime",
    visibility="private",
    opts=pulumi.ResourceOptions(protect=True),
)

platform_demo_apps = github.Repository(
    "platform-demo-apps",
    name="platform-demo-apps",
    description="Demo application for testing the platform",
    visibility="private",
    opts=pulumi.ResourceOptions(protect=True),
)

platform_extensions = github.Repository(
    "platform-extensions",
    name="platform-extensions",
    description="Extensions for the platform",
    visibility="private",
    opts=pulumi.ResourceOptions(protect=True),
)
