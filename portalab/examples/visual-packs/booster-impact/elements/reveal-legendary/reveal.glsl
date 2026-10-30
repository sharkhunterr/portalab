// Impact — a legendary card turned (u_age: seconds, 3.0 s), cel-shaded: green energy flames in two hard tones,
  // inked, licking up all round its slab; inked lime rings rolling away; a great inked four-pointed glint
  // snapping out at its corner, then a smaller one at the other.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float on = step(0.1, age) * step(age, 2.6);
  vec3 ink = vec3(0.07, 0.02, 0.11);
  // the flames, out of the slab's edges (the slab and the card hide what is inside)
  vec2 half_size = vec2(0.24, 0.31);
  float dist = length(max(abs(c) - half_size, 0.0));
  float beat = floor(age * 10.0);
  float flick = fbm(vec2(c.x * 10.0 + c.y * 2.0 + beat * 0.7, c.y * 6.0 - age * 6.0));
  float reach = (0.02 + 0.28 * max(0.0, flick - 0.38)) * smoothstep(0.1, 0.6, age);
  float outside = step(0.0005, dist);
  o = over(o, ink, step(dist, reach + 0.012) * outside * on);
  o = over(o, vec3(0.04, 0.72, 0.28), step(dist, reach) * outside * on);
  o = over(o, vec3(0.17, 1.0, 0.43), step(dist, reach * 0.62) * outside * on);
  o = over(o, vec3(0.8, 1.0, 0.7), step(dist, reach * 0.25) * outside * on);
  // lime rings rolling away, inked
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float wave = 0.3 + (age - fk * 0.35) * 0.5;
    float live = step(fk * 0.35, age) * step(age, 1.4 + fk * 0.35);
    o = over(o, ink, step(abs(r - wave), 0.012) * live);
    o = over(o, vec3(0.83, 0.96, 0.24), step(abs(r - wave), 0.006) * live);
  }
  // the great glint, then a smaller one: inked four-pointed stars snapping out and shrinking
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float at = 0.35 + fk * 1.15;
    float t0 = age - at;
    float size = mix(0.2, 0.12, fk) * step(0.0, t0) * (1.0 - smoothstep(0.0, 0.7, t0)) * smoothstep(-0.02, 0.08, t0);
    vec2 dd = abs(c - mix(vec2(0.3, 0.38), vec2(-0.31, -0.33), fk));
    float star = (dd.x * dd.y / max(size * size, 0.0001)) * 0.8 + (dd.x + dd.y) / max(size, 0.0001);
    o = over(o, ink, step(star, 1.2) * step(0.001, size));
    o = over(o, vec3(1.0), step(star, 0.9) * step(0.001, size));
  }
  // its edges fade out: never the outline of its box
  vec2 edge = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.82, length(edge));
