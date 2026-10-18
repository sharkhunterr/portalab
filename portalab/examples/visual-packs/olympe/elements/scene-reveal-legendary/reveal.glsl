// A legendary card turned: Zeus himself — the clouds parting, a halo of divine gold, sunbeams turning, and
  // bolts of lightning striking round the card one after another (u_age, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.2, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  float cl = fbm(c * 3.0 + vec2(0.0, age * 0.2)) + r * 0.8 - 0.4 - age * 0.25;
  o = over(o, vec3(0.6, 0.62, 0.72), smoothstep(0.3, 0.6, cl) * 0.5 * fade);
  o = over(o, vec3(1.0, 0.88, 0.5), pow(0.5 + 0.5 * sin(a * 12.0 + age * 0.5), 7.0) * smoothstep(0.85, 0.15, r) * 0.5 * fade);
  o = over(o, vec3(1.0, 0.95, 0.75), exp(-r * 6.0) * 0.75 * fade);
  o = over(o, vec3(1.0, 0.85, 0.4), smoothstep(0.012, 0.0, abs(r - 0.36 - 0.01 * sin(a * 24.0 + age * 3.0))) * fade);
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float when = 0.3 + fk * 0.45;
    float on = exp(-max(age - when, 0.0) * 6.0) * step(when, age);
    float side = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 dir = vec2(cos(side), sin(side));
    vec2 nrm = vec2(-dir.y, dir.x);
    float along = dot(c, dir);
    float off = dot(c, nrm) - 0.05 * (noise(vec2(along * 14.0, fk)) - 0.5) - 0.03 * sin(along * 30.0 + fk);
    float seg = step(0.33, along) * step(along, 0.9);
    o = over(o, vec3(0.88, 0.94, 1.0), (smoothstep(0.006, 0.0, abs(off)) + smoothstep(0.04, 0.0, abs(off)) * 0.35) * seg * on * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
