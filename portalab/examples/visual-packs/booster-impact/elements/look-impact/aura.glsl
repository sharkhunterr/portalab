// Impact — round the sealed pack: a pink and violet glow breathing behind it, thin pink rays turning slowly,
  // four-pointed stars flaring at its sides in turn (a stage over the booster's place: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c * vec2(1.3, 1.0));
  float breath = 0.55 + 0.25 * sin(t * 1.9);
  o = over(o, vec3(1.0, 0.18, 0.62), exp(-r * 6.0) * 0.55 * breath);
  o = over(o, vec3(0.55, 0.15, 1.0), exp(-r * 3.2) * 0.3);
  // rays turning slowly round it
  float a = atan(c.y, c.x) + t * 0.15;
  float rays = pow(0.5 + 0.5 * sin(a * 9.0), 18.0) * smoothstep(0.18, 0.3, r) * smoothstep(0.62, 0.32, r);
  o = over(o, vec3(1.0, 0.35, 0.7), rays * 0.35 * breath);
  // stars flaring at its sides, in turn
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float side = mod(fk, 2.0) * 2.0 - 1.0;
    vec2 sp = vec2(side * (0.2 + 0.1 * hash(vec2(fk, 1.0))), (hash(vec2(fk, 2.0)) - 0.5) * 0.55);
    vec2 dd = c - sp;
    float flare = pow(max(0.0, sin(t * 1.3 + fk * 1.7)), 12.0);
    float size = 0.03 + 0.03 * hash(vec2(fk, 3.0));
    float star = exp(-abs(dd.x) * 700.0) * exp(-abs(dd.y) / size * 2.0) + exp(-abs(dd.y) * 700.0) * exp(-abs(dd.x) / size * 2.0);
    o = over(o, vec3(1.0, 0.92, 1.0), clamp(star + exp(-length(dd) * 200.0), 0.0, 1.0) * flare);
  }
  // its edges fade out: never the outline of its box
  vec2 edge = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.7, length(edge));
