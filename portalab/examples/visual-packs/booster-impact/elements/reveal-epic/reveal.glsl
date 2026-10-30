// Impact — an epic card turned (u_age: seconds, 2.4 s), hard-edged: inked pink and white rays bursting out
  // behind it, inked four-pointed sparks flying off, a crosshair snapping on at its corner.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float a = atan(c.y, c.x);
  float on = step(0.08, age) * step(age, 1.9);
  vec3 ink = vec3(0.07, 0.02, 0.11);
  float beat = floor(age * 12.0);
  float grow = smoothstep(0.0, 0.45, age);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float s = a / 6.2832 * (16.0 + fk * 8.0) + fk * 0.31 + hash(vec2(beat, fk)) * 0.12;
    float id = floor(s);
    float len = (0.42 + 0.48 * hash(vec2(id, 7.0 + fk))) * grow * (1.0 - 0.38 * fk);
    float halfw = 0.44 * clamp(1.0 - r / max(len, 0.001), 0.0, 1.0);
    float across = abs(fract(s) - 0.5);
    o = over(o, ink, step(across, halfw) * on);
    o = over(o, mix(vec3(1.0, 0.18, 0.56), vec3(1.0), fk), step(across, halfw - 0.04) * on);
  }
  // sparks flying off: inked four-pointed stars
  for (int k = 0; k < 12; k++) {
    float fk = float(k);
    float dir = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 sp = vec2(cos(dir), sin(dir)) * (0.32 + age * (0.18 + 0.16 * hash(vec2(fk, 2.0))));
    vec2 dd = abs(c - sp);
    float size = 0.028 + 0.02 * hash(vec2(fk, 3.0));
    float star = dd.x * dd.y * 900.0 + (dd.x + dd.y) / size;        // a pinched four-point shape
    float live = step(0.25, age) * step(age, 1.8);
    o = over(o, ink, step(star, 1.25) * live);
    o = over(o, mix(vec3(1.0), vec3(1.0, 0.55, 0.8), step(0.5, hash(vec2(fk, 4.0)))), step(star, 0.85) * live);
  }
  // a crosshair snapping on at its top-right corner
  vec2 cp = c - vec2(0.27, 0.33);
  float cr = length(cp);
  float lit = step(0.5, age) * step(age, 1.9);
  float ring = step(abs(cr - 0.05), 0.004);
  float hair = (step(abs(cp.x), 0.004) * step(abs(cp.y), 0.085) + step(abs(cp.y), 0.004) * step(abs(cp.x), 0.085)) * step(0.022, cr);
  o = over(o, vec3(1.0, 0.18, 0.56), clamp(ring + hair, 0.0, 1.0) * lit);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.82, length(edgeuv));
