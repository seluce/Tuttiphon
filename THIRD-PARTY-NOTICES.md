# Third-party notices

Tuttiphon itself is free software under the GNU Affero General Public License v3.0 or later ([LICENSE](LICENSE)).
The built interface and the Docker image also contain software and data by others, each under its own license.

## In the interface

The build bundles these packages into `web/`. Their full license texts are written by the build into
`web/third-party-licenses.md` (in the running Tuttiphon: `/third-party-licenses.md`), because the minified files no
longer carry the license comments.

| Component | License |
|---|---|
| [Svelte](https://svelte.dev/) | MIT |
| [Lucide](https://lucide.dev/) icons (`@lucide/svelte`) | ISC |
| [clsx](https://github.com/lukeed/clsx) | MIT |
| [Inter](https://rsms.me/inter/) font (`@fontsource-variable/inter`) | SIL Open Font License 1.1 |
| [Tailwind CSS](https://tailwindcss.com/) – its base styles are part of the built CSS | MIT (text below) |

## In the Docker image

| Component | License |
|---|---|
| [Python](https://www.python.org/) 3.12 (base image `python:3.12-slim`, Debian) | PSF-2.0 |
| [FFmpeg](https://ffmpeg.org/) (`ffmpeg`, `ffprobe`; Debian build) | LGPL-2.1-or-later / GPL-2.0-or-later |
| [Chromaprint](https://acoustid.org/chromaprint) (`fpcalc`) | LGPL-2.1-or-later |
| DejaVu fonts (`fonts-dejavu-core`) | Bitstream Vera Fonts license, DejaVu changes in the public domain |
| curl, tzdata | curl license (MIT style), public domain |
| [Pillow](https://python-pillow.org/) 11.3.0 | MIT-CMU (HPND) |
| [mutagen](https://github.com/quodlibet/mutagen) 1.47.0 | GPL-2.0-or-later |
| [cryptography](https://cryptography.io/) 44.0.3 | Apache-2.0 OR BSD-3-Clause |
| [NumPy](https://numpy.org/) 2.5.4 | BSD-3-Clause (bundled parts: 0BSD, MIT, Zlib, CC0-1.0) |
| [Essentia](https://essentia.upf.edu/) (`essentia-tensorflow` 2.1b6.dev1389) | AGPL-3.0-only |
| [TensorFlow](https://www.tensorflow.org/) (inside `essentia-tensorflow`) | Apache-2.0 |
| Essentia AI models in `/app/models` | CC BY-NC-SA 4.0 (see below) |

The full license texts are in the image: for Debian packages in `/usr/share/doc/<package>/copyright`, for Python
packages in `/usr/local/lib/python3.12/site-packages/<package>.dist-info/`.

## AI models

The AI sound analysis uses the Essentia models Discogs-EffNet and its classification heads (the list with checksums is
in `app/ml_worker.py`) by the **Music Technology Group, Universitat Pompeu Fabra**
([essentia.upf.edu/models](https://essentia.upf.edu/models.html)), licensed under
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). They are used unchanged; the image downloads
them while it is built. The license allows non-commercial use only – the MTG offers a commercial license on request.

## Deezer star ratings: dztnr and sptnr

The idea of turning Deezer's popularity rank into star ratings in Navidrome, and the default rank levels, come from
[dztnr](https://github.com/scatolo/dztnr) by scatolo, a fork of [sptnr](https://github.com/krestaino/sptnr) by Kevin
Restaino. Tuttiphon's implementation (`app/deezer.py`) is its own and extends the idea to several accounts; the notice
of the original is reproduced here:

```
MIT License

Copyright (c) 2024 Kevin Restaino

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Tailwind CSS

```
MIT License

Copyright (c) Tailwind Labs, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
