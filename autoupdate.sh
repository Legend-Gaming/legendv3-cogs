#!/bin/bash
url="https://github.com/Cog-Creators/Lavalink-Jars/releases/latest";
current_version_full="$(java -jar Lavalink.jar --version)";
current_version="$(echo $current_version_full | sed -r 's/^Version: ([0-9\.]+)(.*)Build: ([0-9\.]+)(.*)/\1_\3/')"
latest_url="$(curl -LZIs -o /dev/null -w '%{url_effective}' $url)";
latest_version="$(echo "$latest_url" | awk -F/ '{print $NF}')"

if [ "$latest_version" == "$current_version" ]
then
        message="$(date) Already updated to latest version($latest_version)\n"
        printf "$message" >> autoupdate.log;
else
        message="$(date) Current version is $current_version. New version is $latest_version. Updating...\n" ;
        printf "$message" >> autoupdate.log;
        curl -LOz Lavalink.jar "https://github.com/Cog-Creators/Lavalink-Jars/releases/latest/download/Lavalink.jar";
fi
