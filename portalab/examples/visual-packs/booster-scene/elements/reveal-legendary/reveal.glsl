  // A legendary card turned: golden rays turning behind it, a wave of light rolling out with a crest of foam,
  // a caustic flash, then a shower of golden drops falling back (u_age: seconds, 2.8 s in all).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.8, 2.0, age) * smoothstep(0.0, 0.15, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  // the rays, turning
  float rays = pow(0.5 + 0.5 * sin(a * 12.0 + age * 0.9), 6.0) + 0.6 * pow(0.5 + 0.5 * sin(a * 7.0 - age * 0.6), 8.0);
  o = over(o, vec3(1.0, 0.82, 0.38), rays * smoothstep(0.75, 0.12, r) * 0.45 * fade);
  o = over(o, vec3(1.0, 0.93, 0.7), exp(-r * 5.0) * 0.55 * fade);
  // the wave: a ring rolling out, its crest broken into foam
  float front = 0.18 + age * 0.38;
  float crest = smoothstep(0.035, 0.0, abs(r - front - 0.02 * sin(a * 9.0 + age * 6.0)));
  float body = smoothstep(front, front - 0.18, r) * smoothstep(front - 0.32, front - 0.12, r);
  o = over(o, vec3(0.4, 0.9, 1.0), body * 0.35 * fade);
  o = over(o, vec3(1.0, 0.97, 0.85), crest * fade);
  float foam = step(0.72, noise(vec2(a * 18.0, age * 5.0)));
  o = over(o, vec3(1.0), foam * smoothstep(0.06, 0.0, abs(r - front + 0.02)) * fade);
  // the caustic flash as it passes
  vec2 q = c * 7.0 + age;
  float w = fbm(q + fbm(q * 1.3));
  o = over(o, vec3(1.0, 0.95, 0.75), pow(1.0 - abs(w * 2.0 - 1.0), 9.0) * smoothstep(front + 0.05, front - 0.15, r) * smoothstep(front - 0.5, front - 0.2, r) * 0.6 * fade);
  // the shower of golden drops
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    float speed = 0.35 + 0.45 * hash(vec2(fk, 2.0));
    float s = max(age - 0.5 - 0.4 * hash(vec2(fk, 3.0)), 0.0);
    vec2 drop = vec2(cos(ang), sin(ang) * 0.6 + 0.4) * speed * s * 1.6 + vec2(0.0, -0.9 * s * s);
    float size = 0.006 + 0.007 * hash(vec2(fk, 4.0));
    float seen = step(0.001, s) * smoothstep(2.2, 1.4, s + 0.5);
    o = over(o, vec3(1.0, 0.85, 0.4), smoothstep(size, size * 0.2, length(c - drop)) * seen * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.3, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.3, min(edgeuv.y, 1.0 - edgeuv.y));
