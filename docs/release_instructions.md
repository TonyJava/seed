# Release Instructions

To perform a release make sure to do the following.

1. Update the `package.json` file with the most recent version number. Always use MAJOR.MINOR.RELEASE.
1. Run the `docs/scripts/change_log.rb` script and add the changes to the CHANGELOG.md file for the range of time between last release and this release.
   
   
    ruby docs/scripts/change_log.rb --token GITHUB_API_TOKEN --start-date 2017-07-01 --end-date 2017-09-30 

1. Paste the results (except the Accepted Pull Requests) into the CHANGELOG.md. Make sure to cleanup the formatting.
1. Create new PR against develop with the updates.
1. Once develop passes, then create a new PR from develop to master.
1. Draft new Release from Github (https://github.com/SEED-platform/seed/releases).
1. Include list of changes since previous release. (From the console output with the ![Fixed:] text.
1. Verify that the Docker versions are built and pushed to Docker hub (https://hub.docker.com/r/seedplatform/seed/tags/).