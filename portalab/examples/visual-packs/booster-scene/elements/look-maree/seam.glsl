  // Marée — round the cursed chest: a sickly green light leaking from under its lid, breathing, bubbles
  // escaping from its seam now and then (a stage over the booster's place: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec2 seam = vec2(0.0, 0.06);
  vec2 d0 = c - seam;
  float breath = 0.5 + 0.5 * sin(t * 1.3);
  float leak = exp(-d0.y * d0.y * 900.0) * smoothstep(0.2, 0.05, abs(d0.x)) * (0.35 + 0.4 * breath);
  o = over(o, vec3(0.45, 1.0, 0.72), leak * 0.6);
  o = over(o, vec3(0.3, 0.9, 0.6), exp(-dot(d0, d0) * 40.0) * 0.1 * breath);
  for (int k = 0; k < 12; k++) {
    float fk = float(k);
    float life = fract(t * (0.12 + 0.08 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 b = seam + vec2((hash(vec2(fk, 3.0)) - 0.5) * 0.3 + 0.02 * sin(life * 18.0 + fk), life * 0.55);
    float rad = 0.004 + 0.008 * hash(vec2(fk, 4.0));
    float dd = length(c - b);
    float ring = smoothstep(rad, rad * 0.7, dd) * (1.0 - smoothstep(rad * 0.8, rad * 0.35, dd) * 0.7);
    o = over(o, vec3(0.75, 1.0, 0.92), ring * 0.8 * smoothstep(1.0, 0.7, life) * smoothstep(0.0, 0.1, life));
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
