// Reportage — the booster stage: a projection booth in the dark, the projector's beam crossing it with dust,
  // the light flickering, film grain, a strip of film running on each side (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  float flick = 0.92 + 0.08 * hash(vec2(floor(t * 12.0), 3.0));
  o = vec4(vec3(0.07, 0.065, 0.06) * flick, 1.0);
  vec2 src = vec2(asp * 0.45, 0.45);
  vec2 dir = normalize(vec2(-1.0, -0.55));
  vec2 rel = c - src;
  float along = dot(rel, dir);
  float across = abs(rel.x * dir.y - rel.y * dir.x);
  float beam = smoothstep(0.03 + along * 0.22, 0.0, across) * step(0.0, along);
  o = over(o, vec3(1.0, 0.93, 0.78), beam * 0.22 * flick);
  for (int k = 0; k < 40; k++) {
    float fk = float(k);
    vec2 dp = src + dir * (0.1 + 1.6 * hash(vec2(fk, 1.0))) + vec2(dir.y, -dir.x) * (hash(vec2(fk, 2.0)) - 0.5) * 0.25 + vec2(0.0, 0.02 * sin(t * 0.7 + fk));
    o = over(o, vec3(1.0, 0.95, 0.8), exp(-length(c - dp) * 700.0) * 1.4 * beam);
  }
  o = over(o, vec3(1.0, 0.95, 0.85), exp(-length(c - src) * 8.0) * 0.8);
  // where the beam lands: the screen, lit, flickering, a grainy image passing on it
  vec2 sc = c - vec2(-asp * 0.28, -0.16);
  float screen = step(abs(sc.x), 0.3) * step(abs(sc.y), 0.18);
  float picture = 0.55 + 0.25 * fbm(sc * 6.0 + vec2(t * 0.3, 0.0));
  o = over(o, vec3(0.95, 0.9, 0.78) * picture * flick, screen * 0.55);
  o = over(o, vec3(1.0, 0.93, 0.8), exp(-max(abs(sc.x) - 0.3, abs(sc.y) - 0.18) * 30.0) * 0.12 * (1.0 - screen));
  // film strips on the sides, running down, their holes lit
  for (int s = 0; s < 2; s++) {
    float x = (float(s) * 2.0 - 1.0) * asp * 0.46;
    float strip = step(abs(c.x - x), 0.05);
    o = over(o, vec3(0.03, 0.03, 0.03), strip);
    float hole = step(abs(c.x - x), 0.016) * step(0.5, fract((c.y + t * 0.15) * 14.0));
    o = over(o, vec3(0.75, 0.68, 0.55) * flick, hole * 0.5);
  }
  // grain and vignette
  float g = hash(c * 400.0 + floor(t * 24.0));
  o.rgb += (g - 0.5) * 0.05;
  o.rgb *= smoothstep(1.2, 0.3, length(c * vec2(0.8, 1.0)));
