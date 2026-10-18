// A legendary card turned: the mother lode — a huge sheriff's star glinting behind it, sunbeams turning, a
  // storm of gold nuggets whirling round (u_age, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.2, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  float starR = (0.3 + 0.12 * (0.5 + 0.5 * cos(a * 5.0 - 1.5708))) * smoothstep(0.0, 0.6, age);
  o = over(o, mix(vec3(0.8, 0.5, 0.1), vec3(1.0, 0.85, 0.4), 0.5 + 0.5 * sin(a * 5.0)), smoothstep(0.012, 0.0, abs(r - starR)) * fade);
  o = over(o, vec3(1.0, 0.85, 0.4), pow(0.5 + 0.5 * sin(a * 10.0 + age * 0.6), 8.0) * smoothstep(0.8, 0.15, r) * 0.45 * fade);
  o = over(o, vec3(1.0, 0.95, 0.75), exp(-r * 7.0) * 0.7 * fade);
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    float orbit = age * (1.2 + hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)) * 6.2832;
    float rad = 0.3 + 0.2 * hash(vec2(fk, 3.0));
    vec2 at = vec2(cos(orbit) * rad, sin(orbit) * rad * 1.2);
    vec2 q = c - at;
    float size = 0.008 + 0.008 * hash(vec2(fk, 4.0));
    o = over(o, mix(vec3(0.8, 0.55, 0.1), vec3(1.0, 0.9, 0.45), hash(vec2(fk, 5.0))), smoothstep(0.002, 0.0, length(q) - size) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
