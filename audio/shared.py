from pathlib import Path

from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_list

from pylav.core.client import Client

_ = Translator("PyLavPlayer", Path(__file__))


class SharedMethods:
    pylav: Client

    async def _process_play_message(self, context, single_track, total_tracks_enqueue, queries):
        artwork = None
        file = None
        match total_tracks_enqueue:
            case 1:
                if len(queries) == 1:
                    description = _(
                        "{track_name_variable_do_not_translate} enqueued using {service_variable_do_not_translate}."
                    ).format(
                        service_variable_do_not_translate=queries[0].source,
                        track_name_variable_do_not_translate=await single_track.get_track_display_name(with_url=True),
                    )
                elif len(queries) > 1:
                    description = _(
                        "{track_name_variable_do_not_translate} enqueued using {services_variable_do_not_translate}."
                    ).format(
                        services_variable_do_not_translate=humanize_list([q.source for q in queries]),
                        track_name_variable_do_not_translate=await single_track.get_track_display_name(with_url=True),
                    )
                else:
                    description = _("{track_name_variable_do_not_translate} enqueued.").format(
                        track_name_variable_do_not_translate=await single_track.get_track_display_name(with_url=True)
                    )
                artwork = await single_track.artworkUrl()
                file = await single_track.get_embedded_artwork()
            case 0:
                if len(queries) == 1:
                    description = _(
                        "No tracks were found for your query on {service_variable_do_not_translate}."
                    ).format(service_variable_do_not_translate=queries[0].source)
                elif len(queries) > 1:
                    description = _(
                        "No tracks were found for your queries on {services_variable_do_not_translate}."
                    ).format(services_variable_do_not_translate=humanize_list([q.source for q in queries]))
                else:
                    description = _("No tracks were found for your query.")
            case __:
                if len(queries) == 1:
                    description = _(
                        "{number_of_tracks_variable_do_not_translate} tracks enqueued using {service_variable_do_not_translate}."
                    ).format(
                        service_variable_do_not_translate=queries[0].source,
                        number_of_tracks_variable_do_not_translate=total_tracks_enqueue,
                    )
                elif len(queries) > 1:
                    description = _(
                        "{number_of_tracks_variable_do_not_translate} tracks enqueued using {services_variable_do_not_translate}."
                    ).format(
                        services_variable_do_not_translate=humanize_list([q.source for q in queries]),
                        number_of_tracks_variable_do_not_translate=total_tracks_enqueue,
                    )
                else:
                    description = _("{number_of_tracks_variable_do_not_translate} tracks enqueued.").format(
                        number_of_tracks_variable_do_not_translate=total_tracks_enqueue
                    )
        await context.send(
            embed=await self.pylav.construct_embed(
                description=description,
                thumbnail=artwork,
                messageable=context,
            ),
            ephemeral=True,
            file=file,
        )

    async def _process_play_queries(self, context, queries, player, single_track, total_tracks_enqueue, index=None):
        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            *queries, requester=context.author, player=player
        )
        if successful:
            single_track = successful[0]
        total_tracks_enqueue += count
        if count:
            if count == 1:
                await player.add(requester=context.author.id, track=single_track, index=index)
            else:
                await player.bulk_add(requester=context.author.id, tracks_and_queries=successful, index=index)
        return single_track, total_tracks_enqueue
