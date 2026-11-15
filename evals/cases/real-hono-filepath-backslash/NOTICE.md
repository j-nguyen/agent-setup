# Notice

Files in `before/` and `after/` are taken from Hono.

- Repository: https://github.com/honojs/hono
- License: MIT (full text in `before/LICENSE`)
- Copyright (c) 2021 - present, Yusuke Wada and Hono contributors
- `before/` = parent of 48dc87dfd542b9b8f1a442c2d0abab5d13ed4a3b; `after/` = 48dc87dfd542b9b8f1a442c2d0abab5d13ed4a3b ("fix(utils/filepath): filepath supports Windows (#1642)")
- Bug fixed by 82dad6297c90c33c41bf48b4530509a21588ad06 ("fix(serve-static): normalize all backslashes in file paths, not just the first (#4962)"); by then the code had moved into `getFilePathWithoutDefaultDocument`, but the line fixed is the same one.
- `before/package.json` is reduced to its name/version/license/scripts fields; the original has 473 lines of export maps.
