# Official [PyLav](https://github.com/PyLav/Py-Lav) Cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot)
[![Crowdin](https://badges.crowdin.net/pylav/localized.svg)](https://crowdin.com/project/pylav)[![GitHub license](https://img.shields.io/github/license/PyLav/Py-Lav.svg)](https://github.com/PyLav/Py-Lav/blob/master/LICENSE)
[![Support Server](https://img.shields.io/discord/970987707834720266)](https://discord.com/invite/Sjh2TSCYQB)

About Cogs
---------------------------

| Name                                | Version   | Package Name  | Description (Click to expand)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Has Slash commands                                         | Has Context menus commands             | Authors                                   |
|-------------------------------------|-----------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------|----------------------------------------|-------------------------------------------|
| [PyLavPlayer](./audio)              | 1.0.0     | audio         | <details><summary>Load with `[p]load audio`<br/><br/>A Media Player with queue support.<br/></summary><br/>Installing this cog will replace the bundled Audio cog, to revert this simply uninstall this cog.<br/><br/>With support for player history, playlist enqueuing, multiple source searches, multiple queries per command, seek, pause, stop, disconnect, summon, queue repeat<br/><br/>With the context menus you can enqueue spotify songs others are currently listening to or search a message for enqueue-able terms.</details> | Yes (15 root level slash command and 4 text-only commands) | Yes (2, 1 for user and 1 for messages) | [Draper](https://github.com/Drapersniper) |
| [PyLavConfigurator](./audio)        | 1.0.0     | plconfig      | <details><summary>Load with `[p]load plconfig`<br/><br/>Configure PyLav global settings with this Cog.<br/></summary><br/>Used to change toggle the status and behaviour of the managed node as well as changing the localtracks folder.</details>                                                                                                                                                                                                                                                                                           | No  (1 text-only command)                                  | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavMigrator](./plmigrator)       | 1.0.0     | plmigrator    | <details><summary>Load with `[p]load plmigrator`<br/><br/>A Cog which migrates Red's bundled Audio cog settings over to PyLav.<br/></summary><br/>This Cog migrates all playlists, shared global and server settings, with the exception of the per server maximum volume<br/>**DO NOT RUN** run the migration command if you already been used PyLav cogs for a while as it will replace any existing conflicting setting with the values from the Red Audio cog settings.</details>                                                        | No  (1 text-only command)                                  | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavNodes](./plnodes)             | 1.0.0     | plnodes       | <details><summary>Load with `[p]load plnodes`<br/><br/>Configure PyLav nodes with this Cog.<br/></summary><br/>This Cog allows you to add, managed and remove additional nodes from PyLav.</details>                                                                                                                                                                                                                                                                                                                                         | No  (1 text-only command)                                  | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavNotifier](./plnotifier)       | 1.0.0     | plnotifier    | <details><summary>Load with `[p]load plnotifier`<br/><br/>A simple Cog which allows you enable/disable notify events from PyLav.<br/></summary><br/>This Cog allows you to use granularity when disabling/enabling events so that they are sent to the specified channel in your Discord server, useful for server owners who wish to see when a user takes a certain action in PyLav such as enqueueing tracks.</details>                                                                                                                   | No  (1 text-only command)                                  | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavPlaylists](./plplaylists)     | 1.0.0     | plplaylists   | <details><summary>Load with `[p]load plplaylists`<br/><br/>A Cog which allows you to add, manage, remove and share playlists in the User scope.<br/></summary><br/>Playlists created using this Cog can be shared across servers and support all inputs supported by PyLav.</details>                                                                                                                                                                                                                                                        | Yes (1 root level slash command)                           | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavUtils](./plutils)             | 1.0.0     | plutils       | <details><summary>Load with `[p]load plutils`<br/><br/>A handful of commands for Bot Owners to help them see information about the current track and info about the track cache PyLav uses.</summary></details>                                                                                                                                                                                                                                                                                                                              | No  (1 text-only group command)                            | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavLocalFiles](./pllocal)        | 1.0.0     | pllocal       | <details><summary>Load with `[p]load pllocal`<br/><br/>Commands to interact with local media files in the local file folder specified by PyLav.</summary>The local file folder is configured using the PyLavConfigurator Cog, this allows you to play a plethora local files assuming Lavalink supports both the file and codecs, a list of all fully and partially supported files can be seen [here](https://github.com/PyLav/PyLav/blob/master/pylav/localfiles/__init__.py#L12).</details>                                               | Yes (1 root level slash command and 1 text-only command)   | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavEffects](./pleffects)         | 1.0.0     | pleffects     | <details><summary>Load with `[p]load pleffects`<br/><br/>Slash commands to apply filters to the player.</summary>Effects supported are Channel Mix, Distortion, Karaoke, LowPass, Rotation, Timescale, Tremolo, Vibrato and Equalizer using these effects in conjunction, allows you to achieve some really cool effects such as Nightcore and Vaporwave.</details>                                                                                                                                                                          | Yes (1 root level slash command and 1 text-only command)   | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavManagedNode](./plmanagednode) | 1.0.0     | plmanagednode | <details><summary>Load with `[p]load plmanagednode`<br/><br/>Commands to configure Pylav's managed node.</summary>This cog will allow you to enable/disable functionality of PyLav's managed node, the node can be disabled using the PyLavConfigurator Cog</details>                                                                                                                                                                                                                                                                        | No  (1 text-only command)                                  | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavRadio](./plradio)             | 1.0.0     | plradio       | <details><summary>Load with `[p]load plradio`<br/><br/>Play radio stations.</summary>This cog allows you to interact with 30,000+ radio stations.</details>                                                                                                                                                                                                                                                                                                                                                                                  | Yes (1 root level slash command)                           | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavLyrics](./pllyrics)           | 1.0.0     | pllyrics      | <details><summary>Load with `[p]load pllyrics`<br/><br/>Add lyrics to PyLav tracks.</summary>This cog allows you to search for and display track lyrics.</details>                                                                                                                                                                                                                                                                                                                                                                           | No  (1 text-only command)                                  | No                                     | [Draper](https://github.com/Drapersniper) |
| [PyLavController](./plcontroller)   | 1.0.0.rc1 | plcontroller  | <details><summary>Load with `[p]load plcontroller`<br/><br/>A Hydra like controller.</summary>This cog allows you to specify a channel where the bot will listen for messages to enqueue songs, and show a controller that can be interacted with.</details>                                                                                                                                                                                                                                                                                 | No  (1 text-only command)                                  | No                                     | [Draper](https://github.com/Drapersniper) |

* Cogs with version 1.0.0rc0 are considered finished and stable bar feature requests.
* Cogs under version 1.0.0 are considered under development and may change without notice.

Installation
---------------------------
To add the cogs to your Red instance run:
- `[p]repo add PyLav https://github.com/PyLav/Red-Cogs`.
- `[p]cog install PyLav <Package Name>`
- `[p]load <Package Name>`

Documentation
---------------------------

Getting Started
-------------------------------------
Follow [PyLav Setup](https://github.com/PyLav/PyLav/blob/master/SETUP.md)


If you already have a Red instance with PyLav setup then you can do the following
```
[p]load downloader
[p]repo add PyLav https://github.com/PyLav/Red-Cogs
[p]cog install PyLav audio
[p]load audio
```
------------------------------------
System Requirements
------------------------------------
With a locally hosted Postgres server and locally hosted/managed lavalink node (**recommended - Best performance**):
- CPU: 3 cores or more
- RAM: 4GB or more
- Disk Space: 10GB or more (NVME Ideally, SSD OK)

With a locally hosted Postgres server and externally hosted lavalink node (Okay performance):
- CPU: 2 cores or more
- RAM: 3GB or more
- Disk Space: 10GB or more (NVME Ideally, SSD OK)

With an externally hosted Postgres server and locally hosted/managed lavalink node (Poor performance):
- CPU: 2 cores or more
- RAM: 2GB or more
- Disk Space: 10GB or more (SSD)

With an externally hosted Postgres server and externally hosted lavalink node (Worst performance):
- CPU: 1 cores or more
- RAM: 1GB or more
- Disk Space: 10GB or more (SSD)
------------------------------------
Translations
------------------------------------
You can help translating the project into your language here:
[![Crowdin](https://badges.crowdin.net/pylav/localized.svg)](https://crowdin.com/project/pylav)

------------------------------

## Join our support server [![Support Server](https://img.shields.io/discord/970987707834720266?style=social)](https://discord.com/invite/Sjh2TSCYQB)
