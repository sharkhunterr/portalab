// A legendary card turned: a huge eye opening behind it, its pupil narrowing on you, a red strobe, cracks
  // running out, then the eye closing in the dark (u_age: seconds, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.3, age) * smoothstep(0.0, 0.2, age);
  float open = smoothstep(0.1, 0.8, age) * smoothstep(2.9, 2.3, age);
  vec2 e = c * vec2(1.0, 1.0 / max(open * 0.42, 0.001));
  float white = smoothstep(0.6, 0.58, length(e * vec2(1.0, 0.42)));
  float iris = smoothstep(0.22, 0.2, length(c));
  float slit = smoothstep(0.05 - 0.035 * smoothstep(0.6, 1.4, age), 0.0, abs(c.x)) * iris;
  float veins = smoothstep(0.55, 0.9, fbm(c * 9.0)) * smoothstep(0.2, 0.5, length(c));
  o = over(o, vec3(0.0), smoothstep(0.2, 0.8, length(c)) * 0.7 * fade);
  o = over(o, vec3(0.85, 0.78, 0.72) - veins * vec3(0.0, 0.5, 0.5), white * fade);
  o = over(o, mix(vec3(0.95, 0.15, 0.05), vec3(0.4, 0.0, 0.0), smoothstep(0.0, 0.22, length(c))), white * iris * fade);
  o = over(o, vec3(0.0), white * slit * fade);
  float strobe = step(0.5, fract(age * 10.0)) * smoothstep(0.5, 0.8, age) * smoothstep(1.5, 1.1, age);
  o = over(o, vec3(0.8, 0.0, 0.0), strobe * 0.35);
  float a = atan(c.y, c.x);
  float crack = 0.0;
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    float dir = fk * 0.898 + hash(vec2(fk, 1.0)) * 0.5;
    crack += smoothstep(0.01, 0.0, abs(sin(a - dir - 0.12 * sin(length(c) * 30.0 + fk))) * length(c)) * step(0.3, length(c)) * step(length(c), (age - 0.6) * 0.8);
  }
  o = over(o, vec3(1.0, 0.85, 0.8), clamp(crack, 0.0, 1.0) * fade);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
