import { createLucideIcon, type IconNode } from "lucide-react";

/**
 * issue 130: the twelve constellations of the zodiac as icons — their brightest stars (dots) joined by the
 * lines star charts draw, simplified to read at 16 pixels. Same stroke as the other icons.
 */
type Star = [number, number];

function constellation(name: string, lines: Star[][], extra: IconNode = []) {
  const stars = new Map<string, Star>();
  for (const line of lines) for (const star of line) stars.set(star.join(","), star);
  const node: IconNode = [
    ...lines.map(
      (line, i) =>
        [
          "path",
          { d: `M${line.map(([x, y]) => `${x} ${y}`).join(" L")}`, key: `l${i}`, strokeWidth: 1.4 },
        ] as IconNode[number],
    ),
    ...[...stars.values()].map(
      ([cx, cy], i) => ["circle", { cx, cy, r: 1.5, fill: "currentColor", key: `s${i}` }] as IconNode[number],
    ),
    ...extra,
  ];
  return createLucideIcon(name, node);
}

export const ZODIAC_ICONS = {
  "zodiac-aries": constellation("ZodiacAries", [
    [
      [3, 11],
      [10, 7],
      [15, 8],
      [21, 13],
    ],
  ]),
  "zodiac-taurus": constellation("ZodiacTaurus", [
    [
      [3, 4],
      [9, 11],
      [12, 14],
      [15, 11],
      [21, 5],
    ],
    [
      [12, 14],
      [11, 21],
    ],
  ]),
  "zodiac-gemini": constellation("ZodiacGemini", [
    [
      [8, 3],
      [6, 12],
      [4, 20],
    ],
    [
      [15, 4],
      [16, 12],
      [18, 20],
    ],
    [
      [6, 12],
      [16, 12],
    ],
  ]),
  "zodiac-cancer": constellation("ZodiacCancer", [
    [
      [9, 3],
      [12, 11],
      [7, 20],
    ],
    [
      [17, 4],
      [12, 11],
      [18, 20],
    ],
  ]),
  "zodiac-leo": constellation("ZodiacLeo", [
    [
      [4, 16],
      [4, 10],
      [6, 5],
      [11, 4],
      [12, 9],
      [18, 10],
      [21, 16],
      [16, 17],
      [4, 16],
    ],
  ]),
  "zodiac-virgo": constellation("ZodiacVirgo", [
    [
      [3, 5],
      [8, 9],
      [12, 10],
      [16, 7],
      [21, 4],
    ],
    [
      [8, 9],
      [9, 16],
      [5, 21],
    ],
    [
      [12, 10],
      [14, 17],
      [19, 20],
    ],
  ]),
  "zodiac-libra": constellation("ZodiacLibra", [
    [
      [12, 3],
      [5, 10],
      [19, 10],
      [12, 3],
    ],
    [
      [5, 10],
      [4, 19],
    ],
    [
      [19, 10],
      [20, 18],
    ],
  ]),
  "zodiac-scorpio": constellation("ZodiacScorpio", [
    [
      [2, 3],
      [4, 7],
      [6, 3],
    ],
    [
      [4, 7],
      [7, 9],
      [9, 13],
      [10, 17],
      [13, 20],
      [17, 20],
      [20, 17],
      [21, 13],
    ],
  ]),
  "zodiac-sagittarius": constellation("ZodiacSagittarius", [
    [
      [4, 14],
      [8, 10],
      [13, 11],
      [13, 17],
      [8, 18],
      [4, 14],
    ],
    [
      [13, 11],
      [17, 7],
      [21, 10],
      [18, 17],
      [13, 17],
    ],
  ]),
  "zodiac-capricorn": constellation("ZodiacCapricorn", [
    [
      [2, 8],
      [8, 11],
      [13, 18],
      [18, 15],
      [22, 6],
      [14, 10],
      [2, 8],
    ],
  ]),
  "zodiac-aquarius": constellation("ZodiacAquarius", [
    [
      [3, 6],
      [7, 8],
      [11, 5],
      [15, 8],
    ],
    [
      [11, 5],
      [10, 12],
      [13, 15],
      [11, 20],
    ],
    [
      [13, 15],
      [18, 17],
      [21, 21],
    ],
  ]),
  "zodiac-pisces": constellation("ZodiacPisces", [
    [
      [4, 5],
      [8, 11],
      [12, 20],
      [16, 13],
      [21, 10],
    ],
  ]),
} as const;

export const ZODIAC_SIGNS = [
  "aries",
  "taurus",
  "gemini",
  "cancer",
  "leo",
  "virgo",
  "libra",
  "scorpio",
  "sagittarius",
  "capricorn",
  "aquarius",
  "pisces",
] as const;
