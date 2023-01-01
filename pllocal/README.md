# PyLavLocalFiles

## Text Commands
- `[p]localset`
  - Configure cog settings
- `[p]localset version`
  - Show the version of the Cog and it's PyLav dependencies
- `[p]localset updates` | Bot Owner Only
  - Update the track list for `/local`
  - Use this if you changed the local files since the cog was loaded.

## Slash Commands
- `/local <entry> [recursive]`
  - Enqueue a local file or directory
  - `<entry>` is the name of the file or directory to enqueue, it will autocomplete based on input.
  - `[recursive]` is a boolean to enqueue all files in a directory tree recursively
