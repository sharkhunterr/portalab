// Fanzine — the booster stage: a photocopied collage on black toner — torn scraps of page shifting a little at
  // each copy, a highlighter's stripes, the toner's grain, the copier's light passing over it all (a stage:
  // gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  float copy = floor(t * 4.0);
  o = vec4(0.07, 0.07, 0.07, 1.0);
  for (int k = 0; k < 14; k++) {
    float fk = float(k);
    vec2 pp = vec2((hash(vec2(fk, 1.0)) - 0.5) * asp * 1.1, hash(vec2(fk, 2.0)) - 0.5) + (vec2(hash(vec2(fk, copy)), hash(vec2(copy, fk))) - 0.5) * 0.004;
    float an = (hash(vec2(fk, 3.0)) - 0.5) * 0.6;
    vec2 q = mat2(cos(an), -sin(an), sin(an), cos(an)) * (c - pp);
    vec2 sz = vec2(0.08 + 0.1 * hash(vec2(fk, 4.0)), 0.05 + 0.08 * hash(vec2(fk, 5.0)));
    float edge = 0.006 * (noise(q * 90.0 + fk) - 0.5);
    float inside = step(max(abs(q.x) - sz.x, abs(q.y) - sz.y), edge);
    float tone = mod(fk, 3.0);
    vec3 paper = tone < 1.0 ? vec3(0.95, 0.94, 0.9) : tone < 2.0 ? vec3(0.62, 0.62, 0.6) : vec3(0.85, 0.84, 0.8);
    vec2 cell = fract(q * 160.0) - 0.5;
    float dots = step(length(cell), 0.3 * (0.5 + 0.5 * sin(q.x * 30.0 + fk)));
    o = over(o, paper, inside);
    o = over(o, vec3(0.07, 0.07, 0.07), inside * dots * step(1.5, tone));
    o = over(o, vec3(0.07, 0.07, 0.07), inside * step(abs(fract(q.y * 40.0) - 0.5), 0.08) * step(abs(q.x), sz.x * 0.7) * step(tone, 0.5) * step(q.y, sz.y * 0.5));
    o = over(o, vec3(1.0, 0.95, 0.15), inside * step(abs(q.y + sz.y * 0.4), 0.012) * step(mod(fk, 4.0), 0.5) * 0.7);
  }
  o = over(o, vec3(1.0, 0.2, 0.55), smoothstep(0.006, 0.0, abs(length((c - vec2(asp * 0.18, -0.2)) * vec2(1.0, 1.6)) - 0.16)) * 0.9);
  o.rgb += (hash(floor(c * 240.0) + copy) - 0.5) * 0.09;
  float bar = fract(t / 3.0) * (asp + 0.6) - asp * 0.5 - 0.3;
  o = over(o, vec3(0.85, 1.0, 0.9), exp(-abs(c.x - bar) * 40.0) * 0.5);
