# Cleverbotcog (Red V3)
## Prerequisites:
1. Red-bot with downloader cog. Downloader cog comes with red-bot by default.
2. Python packages: selenium, psutil. Can be installed using `python3 -m pip install selenium psutil`
3. Chrome or firefox browser installed.
4. Webdriver for chrome or firefox depending on browser. Note that appropriate webdriver should be chosen depending on browser and its version; there are different webdrivers for each version of chrome and firefox


## Instructions:
(Replace `[p]` with prefix for your bot)
1. Add repository using `[p]repo add legend https://github.com/Legend-Gaming`. You need to have downloader cog from red loaded for this.
2. Install cog using `[p]cog install legend cleverbot`.
3. Load cog using `[p] load cleverbot`.
4. Set path to webdriver using `[p]setcleverbot <browser_name> webdriver <path>`. Replace <browser_name> with chrome or firefox and path with absolute path to webdriver execuatable. If you have multiple version of browser installed you may need to set path to correct executable using `[p]setcleverbot <browser_name> executable <path>.
5. Connect to cleverbot url using `[p]cleverbot connect`
6. Send message to bot using either `[p]cleverbot say <message>` or tagging the bot followed by message: `@mybot hello`
