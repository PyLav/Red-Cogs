# PyLavEqualizer

## Text Commands
- `[p]eqset` | Requires manage server permissions or server owner
  - Configure the Player behaviour when an equalizer is set
- `[p]eqset version`
  - Show the version of the Cog and its PyLav dependencies
- `[p]eqset list persist`
  - Persist the last used preset

## Slash Commands
- `/eq`
  - Apply an Equalizer preset to the player
- `/eq bassboost <level>`
  - Apply a Bassboost preset to the player
  - `<level>` - The level of the bassboost preset
    - Can be one of the following:
      - `Maximum`
      - `Insane`
      - `Extreme`
      - `Very High`
      - `High`
      - `Medium`
      - `Fine Tuned`
      - `Cut-off`
      - `Off`
- `/eq piano`
  - Apply a Piano preset to the player
- `/eq rock`
  - Apply a Rock preset to the player
- `/eq reset`
  - Remove any Equalizer presets applied to the player
- `/eq custom <name> [description] [band, ...]`
  -  Apply a custom Equalizer preset to the player
  - `<name>` - The name of the custom preset
  - `[description]` - The description of the custom preset
  - `[bands]` - The bands of the custom preset
    - Values for bands can range from `-0.25` to `1.0`
    - If not provided it will use the currently set value or not set.
  - `[save]` - Whether to save the custom preset
    - Can be `true` or `false`
- `/eq save`
  - Save the current Equalizer settings as a preset (Currently there is no way to customize or reapply once saved)
