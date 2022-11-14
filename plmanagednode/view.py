from __future__ import annotations

import re
from pathlib import Path

import asyncstdlib
import discord
import netaddr
from netaddr import IPAddress, IPNetwork
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_list

from pylav.types import BotT, CogT, InteractionT

_ = Translator("PyLavManagedNode", Path(__file__))


class ConfigureIPRotationView(discord.ui.View):
    """
    A secure ``discord.ui.View`` used to configure the managed nodes IP Rotation.
    """

    def __init__(
        self,
        bot: BotT,
        cog: CogT,
        prefix: str,
        timeout: int = 180,
    ):
        self.bot = bot
        self.cog = cog
        self.prefix = prefix
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: InteractionT) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(_("You are not authorized to interact with this"), ephemeral=True)
            return False
        return True

    @discord.ui.button(
        label=_("Configure IP Rotation"),
        style=discord.ButtonStyle.grey,
    )
    async def add_ip_block(self, interaction: InteractionT, button: discord.ui.Button):
        return await interaction.response.send_modal(
            ConfigureIPRotationModal(bot=self.bot, cog=self.cog, prefix=self.prefix)
        )


class ConfigureGoogleAccountView(discord.ui.View):
    """
    A secure ``discord.ui.View`` used to configure the Google account for the node.
    """

    def __init__(self, bot: BotT, cog: CogT, prefix: str, timeout: int = 180):
        self.bot = bot
        self.cog = cog
        self.prefix = prefix
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: InteractionT) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(_("You are not authorized to interact with this"), ephemeral=True)
            return False
        return True

    @discord.ui.button(
        label=_("Link Google Account"),
        style=discord.ButtonStyle.grey,
    )
    async def link_account(self, interaction: InteractionT, button: discord.ui.Button):
        return await interaction.response.send_modal(
            ConfigureGoogleAccountModal(bot=self.bot, cog=self.cog, prefix=self.prefix)
        )


class ConfigureHTTPProxyView(discord.ui.View):
    """
    A secure ``discord.ui.View`` used to configure a HTTP Proxy for the node.
    """

    def __init__(
        self,
        bot: BotT,
        cog: CogT,
        prefix: str,
        timeout: int = 180,
    ):
        self.bot = bot
        self.cog = cog
        self.prefix = prefix
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: InteractionT) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(_("You are not authorized to interact with this"), ephemeral=True)
            return False
        return True

    @discord.ui.button(
        label=_("Configure HTTP Proxy"),
        style=discord.ButtonStyle.grey,
    )
    async def configure_proxy(self, interaction: InteractionT, button: discord.ui.Button):
        return await interaction.response.send_modal(
            ConfigureHTTPProxyModal(bot=self.bot, cog=self.cog, prefix=self.prefix)
        )


class ConfigureIPRotationModal(discord.ui.Modal):
    """A secure ``discord.ui.Modal`` used to configure the managed nodes IP Rotation"""

    def __init__(
        self,
        bot: BotT,
        cog: CogT,
        prefix: str,
    ):
        self.bot = bot
        self.cog = cog
        self.prefix = prefix

        super().__init__(title=_("IP Rotation Configurator"))

        self.ip_blocks = discord.ui.TextInput(
            label=_("IP Blocks"),
            style=discord.TextStyle.long,
            required=True,
            placeholder=_("1.0.0.0/8,...,... - Comma separated list of IP blocks"),
        )

        self.strategy = discord.ui.TextInput(
            label=_("Rotation strategy"),
            style=discord.TextStyle.long,
            required=True,
            placeholder="RotateOnBan | LoadBalance | NanoSwitch | RotatingNanoSwitch",
            max_length=18,
            min_length=10,
        )

        self.retry_limit = discord.ui.TextInput(
            label=_("Retry limit"),
            style=discord.TextStyle.short,
            required=False,
            placeholder=_("-1 = default, 0 = infinity, >0 = number of retries"),
            min_length=1,
            max_length=3,
        )
        self.excluded_ips = discord.ui.TextInput(
            label=_("IPs to exclude"),
            required=False,
            style=discord.TextStyle.short,
            placeholder=_("Comma separated list of IP to exclude from rotation"),
        )

        self.search_trigger = discord.ui.TextInput(
            label=_("Search trigger rotation"),
            style=discord.TextStyle.short,
            required=False,
            placeholder=_("0 or 1 (0 = disabled, 1 = enabled)"),
            min_length=1,
            max_length=1,
        )
        self.add_item(self.ip_blocks)
        self.add_item(self.strategy)
        self.add_item(self.retry_limit)
        self.add_item(self.search_trigger)
        self.add_item(self.excluded_ips)

    async def on_submit(self, interaction: InteractionT):
        if not await self.bot.is_owner(
            interaction.user
        ):  # Prevent non-bot owners from somehow acquiring and saving the modal.
            return await interaction.response.send_message(
                _("You are not authorized to interact with this"), ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)

        send_method = interaction.followup.send
        if self.ip_blocks.value:
            try:
                ip_blocks = await asyncstdlib.list(
                    asyncstdlib.map(str, asyncstdlib.map(IPNetwork, set(self.ip_blocks.value.split(","))))
                )
            except netaddr.core.AddrFormatError as exc:
                return await send_method(
                    embed=await self.bot.lavalink.construct_embed(
                        description=_("Invalid IP block - {error}").format(exc),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                    wait=True,
                )
        else:
            ip_blocks = []

        if not ip_blocks:

            return await send_method(
                embed=await self.bot.lavalink.construct_embed(
                    description=_("No IP blocks were provided"),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
        if self.ip_blocks.value:
            try:
                excluded_ips = await asyncstdlib.list(
                    asyncstdlib.map(str, asyncstdlib.map(IPAddress, set(self.ip_blocks.value.split(","))))
                )
            except netaddr.core.AddrFormatError as exc:

                return await send_method(
                    embed=await self.bot.lavalink.construct_embed(
                        description=_("Invalid IP address - {error}").format(exc),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                    wait=True,
                )
        else:
            excluded_ips = []

        strategy = self.strategy.value.lower().strip()
        stategy_mapping = {
            "rotateonban": "RotateOnBan",
            "loadbalance": "LoadBalance",
            "nanoswitch": "NanoSwitch",
            "rotatingnanoswitch": "RotatingNanoSwitch",
        }
        if strategy not in stategy_mapping:
            return await send_method(
                embed=await self.bot.lavalink.construct_embed(
                    description=_("Invalid strategy, must be one of: {options}").format(
                        options=humanize_list(list(stategy_mapping.values()))
                    ),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
        strategy = stategy_mapping[strategy]
        try:
            retry_limit = int(self.retry_limit.value.strip() or "-1")
            if retry_limit < -1:
                raise ValueError
        except ValueError:
            return await send_method(
                embed=await self.bot.lavalink.construct_embed(
                    description=_("Invalid retry limit, must be a number greater than or equals to -1"),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )

        try:
            search_trigger = int(self.search_trigger.value.strip() or "1")
            if search_trigger not in [0, 1]:
                raise ValueError
            search_trigger = bool(search_trigger)
        except ValueError:
            return await send_method(
                embed=await self.bot.lavalink.construct_embed(
                    description=_("Invalid search trigger, must be 0 or 1"),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )

        config = self.bot.lavalink.node_db_manager.bundled_node_config()
        yaml_data = await config.fetch_yaml()
        yaml_data["lavalink"]["server"]["ratelimit"] = {
            "ipBlocks": ip_blocks,
            "strategy": strategy,
            "retryLimit": retry_limit,
            "excludedIps": excluded_ips,
            "searchTriggersFail": search_trigger,
        }
        await config.update_yaml(yaml_data)
        return await send_method(
            embed=await self.bot.lavalink.construct_embed(
                description=_(
                    "IP rotation configuration saved."
                ).format(prefix=self.prefix),
                messageable=interaction,
            ),
            ephemeral=True,
            wait=True,
        )


class ConfigureGoogleAccountModal(discord.ui.Modal):
    """A secure ``discord.ui.Modal`` used to add a Google account to the node"""

    def __init__(
        self,
        bot: BotT,
        cog: CogT,
        prefix: str,
    ):
        self.bot = bot
        self.cog = cog
        self.prefix = prefix

        super().__init__(title=_("Google Account Configurator"))

        self.email = discord.ui.TextInput(
            label=_("Email address"),
            style=discord.TextStyle.short,
            required=True,
            placeholder=_("Your Google account email"),
            min_length=4,
        )

        self.password = discord.ui.TextInput(
            label=_("password"),
            style=discord.TextStyle.short,
            required=True,
            placeholder=_("If you have 2FA you will need an app password"),
            min_length=8,
            max_length=100,
        )

        self.add_item(self.email)
        self.add_item(self.password)

    async def on_submit(self, interaction: InteractionT):
        if not await self.bot.is_owner(
            interaction.user
        ):  # Prevent non-bot owners from somehow acquiring and saving the modal.
            return await interaction.response.send_message(
                _("You are not authorized to interact with this"), ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)

        send_method = interaction.followup.send
        if re.match(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", self.email.value) is None:
            return await send_method(
                embed=await self.bot.lavalink.construct_embed(
                    description=_("Invalid email address"),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )

        await self.bot.set_shared_api_tokens("google", email=self.email.value, password=self.password.value)
        return await send_method(
            embed=await self.bot.lavalink.construct_embed(
                description=_("Google account linked.").format(
                    prefix=self.prefix
                ),
                messageable=interaction,
            ),
            ephemeral=True,
            wait=True,
        )


class ConfigureHTTPProxyModal(discord.ui.Modal):
    """A secure ``discord.ui.Modal`` used to configure a HTTP Proxy for the node"""

    def __init__(
        self,
        bot: BotT,
        cog: CogT,
        prefix: str,
    ):
        self.bot = bot
        self.cog = cog
        self.prefix = prefix

        super().__init__(title=_("HTTP Proxy Configurator"))

        self.host = discord.ui.TextInput(
            label=_("Hostname"),
            style=discord.TextStyle.short,
            required=True,
            placeholder=_("Hostname of the proxy, (ip or domain or localhost)"),
        )

        self.port = discord.ui.TextInput(
            label=_("Proxy port"),
            style=discord.TextStyle.short,
            required=True,
            placeholder=_("Proxy port, 3128 is the default for squidProxy"),
            min_length=1,
            max_length=5,
        )

        self.user = discord.ui.TextInput(
            label=_("User"),
            style=discord.TextStyle.long,
            required=False,
            placeholder=_("Optional user for basic authentication fields, leave blank if you don't use basic auth"),
        )
        self.password = discord.ui.TextInput(
            label=_("Password"),
            style=discord.TextStyle.long,
            required=False,
            placeholder=_("Optional password for basic authentication fields, leave blank if you don't use basic auth"),
        )
        self.add_item(self.host)
        self.add_item(self.port)
        self.add_item(self.user)
        self.add_item(self.password)

    async def on_submit(self, interaction: InteractionT):
        if not await self.bot.is_owner(
            interaction.user
        ):  # Prevent non-bot owners from somehow acquiring and saving the modal.
            return await interaction.response.send_message(
                _("You are not authorized to interact with this"), ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        send_method = interaction.followup.send
        try:
            port = int(self.port.value.strip())
            if not (0 <= port <= 65536):
                raise ValueError
        except ValueError:
            return await send_method(
                embed=await self.bot.lavalink.construct_embed(
                    description=_("Invalid port, must be a number between 0 and 65536"),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
        config = self.bot.lavalink.node_db_manager.bundled_node_config()
        yaml_data = await config.fetch_yaml()
        yaml_data["lavalink"]["server"]["httpConfig"] = {
            "proxyHost": self.host.value,
            "proxyPort": port,
            "proxyUser": self.user.value,
            "proxyPassword": self.password.value,
        }
        await config.update_yaml(yaml_data)
        return await send_method(
            embed=await self.bot.lavalink.construct_embed(
                description=_(
                    "HTTP proxy configuration saved."
                ).format( prefix=self.prefix),
                messageable=interaction,
            ),
            ephemeral=True,
            wait=True,
        )
