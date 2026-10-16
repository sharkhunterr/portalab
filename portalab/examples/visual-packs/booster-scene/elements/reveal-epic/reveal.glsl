  // An epic card turned: the water whirling round it, a violet glow at its heart, spray flung outwards.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.5, age) * smoothstep(0.0, 0.2, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  float spin = a + 2.6 / (r + 0.15) - age * 3.2;
  float arms = pow(0.5 + 0.5 * sin(spin * 3.0 + fbm(c * 5.0 + age) * 2.0), 3.0);
  float band = smoothstep(0.12, 0.22, r) * smoothstep(0.62, 0.3, r);
  vec3 water = mix(vec3(0.2, 0.75, 0.9), vec3(0.85, 0.35, 0.95), smoothstep(0.15, 0.5, r));
  o = over(o, water, arms * band * 0.7 * fade);
  o = over(o, vec3(1.0, 0.95, 1.0), pow(arms, 6.0) * band * 0.7 * fade);
  o = over(o, vec3(0.75, 0.3, 0.95), exp(-r * 6.0) * 0.4 * fade);
  for (int k = 0; k < 24; k++) {
    float fk = float(k);
    float s = fract(age * 0.9 + hash(vec2(fk, 1.0)));
    float ang = hash(vec2(fk, 2.0)) * 6.2832 - age * 2.0;
    vec2 drop = vec2(cos(ang), sin(ang)) * (0.3 + s * 0.45);
    float size = 0.008 * (1.0 - s);
    o = over(o, vec3(0.95, 0.8, 1.0), smoothstep(size, 0.0, length(c - drop)) * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.3, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.3, min(edgeuv.y, 1.0 - edgeuv.y));
