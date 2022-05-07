[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Drapersniper/Audio/master.svg)](https://results.pre-commit.ci/latest/github/Drapersniper/Audio/master)
[![Crowdin](https://badges.crowdin.net/mediaplayer/localized.svg)](https://crowdin.com/project/mediaplayer)
[![GitHub license](https://img.shields.io/github/license/Drapersniper/Py-Lav.svg)](https://github.com/Drapersniper/Py-Lav/blob/master/LICENSE)
[![Support Server](https://img.shields.io/discord/970987707834720266)](https://discord.com/invite/Sjh2TSCYQB)

# Official [PyLav](https://github.com/Drapersniper/Py-Lav) Cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot)

About Cogs
---------------------------

| Name              | Version | Package Name | Description (Click to expand)                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Has Slash commands                                | Has Context menus commands              | Authors                                         |
|-------------------|---------|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------|-----------------------------------------|-------------------------------------------------|
| PyLavPlayer       | 0.0.1a  | audio        | <details><summary>Load with `[p]load audio`<br/><br/>A Media Player with queue support.<br/></summary><br/>Installing this cog will replace the bundled Audio cog, to revert this simply uninstall this cog.<br/><br/>With support for player history, playlist enqueuing, multiple source searches, multiple queries per command, seek, pause, stop, disconnect, summon, queue repeat</details>                                                                                 | Yes (14 slash [hybrid] and 3 text-only commands)  | Yes (one for user and one for messages) | [Drapersniper](https://github.com/Drapersniper) |
| PyLavConfigurator | 0.0.1a  | plconfig     | <details><summary>Load with `[p]load plconfig`<br/><br/>Configure PyLav global settings with this Cog.<br/></summary><br/>Used to change toggle the status and behaviour of the managed node as well as changing the localtracks folder.</details>                                                                                                                                                                                                                               | No  (1 text-only command with 5 subcommands)      | No                                      | [Drapersniper](https://github.com/Drapersniper) |
| PyLavMigrator     | 0.0.1a  | plmigrator   | <details><summary>Load with `[p]load plmigrator`<br/><br/>A Cog which migrate Red's bundled Audio cog settings over to PyLav.<br/></summary><br/>This Cog migrates all playlists, shared global and server settings, with the exception of the per server maximum volume<br/>**DO NOT RUN** run the migration command if you already been used PyLav cogs for a while as it will replace any existing conflicting setting with the values from the Audio cog settings.</details> | No  (1 text-only command)                         | No                                      | [Drapersniper](https://github.com/Drapersniper) |
| PyLavNodes        | 0.0.1a  | plnodes      | <details><summary>Load with `[p]load plnodes`<br/><br/>Configure PyLav nodes with this Cog.<br/></summary><br/>This Cog allows you to add, managed and remove additional nodes from PyLav.</details>                                                                                                                                                                                                                                                                             | No  (1 text-only command with 3 subcommands)      | No                                      | [Drapersniper](https://github.com/Drapersniper) |
| PyLavNotifier     | 0.0.1a  | plnotifier   | <details><summary>Load with `[p]load plnotifier`<br/><br/>A Simple Cog which allows you enable/disable notify events from PyLav.<br/></summary><br/>This Cog allows you to granuraly disable/enable events so that they are sent to the specified channel in your Discord server, useful for server owners who wish to see when a user takes a certain action in PyLav such as enqueueing tracks.</details>                                                                      | No  (1 text-only command with 2 subcommands)      | No                                      | [Drapersniper](https://github.com/Drapersniper) |
| PyLavPlaylists    | 0.0.1a  | plplaylists  | <details><summary>Load with `[p]load plplaylists`<br/><br/>A Cog which allows you to add, managed, remove and share playlists in the User scope.<br/></summary><br/>Playlists created using this Cog can be shared across servers and support all inputs supported by PyLav.</details>                                                                                                                                                                                           | Yes (1 slash [hybrid] command with 4 subcommands) | No                                      | [Drapersniper](https://github.com/Drapersniper) |
| PyLavUtils        | 0.0.1a  | plutils      | <summary>Load with `[p]load plutils`<br/><br/>A handul of commands for Bot Owners to help them see information about the current track and info about the track cache PyLav uses.</summary>                                                                                                                                                                                                                                                                                      | No  (1 text-only command with 9 subcommands)      | No                                      | [Drapersniper](https://github.com/Drapersniper) |


Installation
---------------------------
To add the cogs to your Red instance run:
- `[p]repo add PyLav https://github.com/Drapersniper/PyLav-Cogs`.
- `[p]cog install PyLav <Package Name>`
- `[p]load <Package Name>`

Documentation
---------------------------

Getting Started
-------------------------------------

Translations
------------------------------------
You can help translating the project into your language here:

[![Crowdin](https://badges.crowdin.net/mediaplayer/localized.svg)](https://crowdin.com/project/mediaplayer).

Shared code translation can be for here:

[![Crowdin](https://badges.crowdin.net/pylavshared/localized.svg)](https://crowdin.com/project/pylavshared)


## Join our support server [![Support Server](https://img.shields.io/discord/970987707834720266?style=social)](https://discord.com/invite/Sjh2TSCYQB)
