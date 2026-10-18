// A legendary card turned: everything overloads behind it — neon arcs crackling out, a wireframe city
  // drawing itself on the horizon, a yellow shockwave, glitch slices and a rain of sparks (u_age: seconds, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.2, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  // the wireframe city on the horizon, drawing itself from the middle out
  float horizon = -0.18;
  float bx = floor(c.x * 14.0);
  float bh = horizon + 0.1 + 0.25 * hash(vec2(bx, 1.0));
  float outline = (smoothstep(0.004, 0.0, abs(c.y - bh)) + smoothstep(0.004, 0.0, abs(fract(c.x * 14.0) - 0.02) / 14.0 * 14.0 * 0.05)) * step(horizon, c.y) * step(c.y, bh + 0.002);
  float drawn = step(abs(c.x), age * 0.4);
  o = over(o, vec3(0.1, 0.95, 1.0), clamp(outline, 0.0, 1.0) * drawn * 0.7 * fade);
  o = over(o, vec3(1.0, 0.1, 0.6), smoothstep(0.004, 0.0, abs(c.y - horizon)) * drawn * fade);
  // neon arcs crackling out
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    float t0 = 0.2 + fk * 0.3;
    float on = step(t0, age) * step(age, t0 + 0.22);
    float dir = hash(vec2(fk, 4.0)) * 6.2832;
    float seg = floor(r * 14.0);
    float jag = dir + 0.3 * (hash(vec2(fk, seg + floor(age * 20.0))) - 0.5);
    float arc = smoothstep(0.006, 0.0, abs(sin(a - jag)) * r) * step(0.18, r) * step(r, 0.7) * step(0.0, cos(a - jag));
    o = over(o, mix(vec3(1.0, 0.2, 0.7), vec3(0.3, 1.0, 1.0), mod(fk, 2.0)), arc * on);
  }
  // the yellow shockwave and the core light
  o = over(o, vec3(0.99, 0.93, 0.04), smoothstep(0.015, 0.0, abs(r - (0.12 + age * 0.4))) * smoothstep(1.4, 0.6, age) * fade);
  o = over(o, vec3(1.0, 0.95, 0.7), exp(-r * 8.0) * 0.6 * fade);
  // glitch slices
  float row = floor(c.y * 30.0);
  float slice = step(0.88, hash(vec2(row, floor(age * 14.0)))) * smoothstep(0.6, 0.2, abs(c.y));
  o = over(o, mix(vec3(1.0, 0.0, 0.4), vec3(0.0, 0.95, 1.0), hash(vec2(row, 2.0))), slice * 0.35 * fade);
  // the rain of sparks
  for (int k = 0; k < 28; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 1.0)) - 0.5) * 1.3, 0.6 - fract(age * (0.5 + 0.4 * hash(vec2(fk, 2.0))) + hash(vec2(fk, 3.0))) * 1.3);
    o = over(o, mix(vec3(0.99, 0.93, 0.04), vec3(1.0, 0.3, 0.7), hash(vec2(fk, 4.0))), exp(-length((c - sp) * vec2(1.0, 0.4)) * 220.0) * step(0.4, age) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
