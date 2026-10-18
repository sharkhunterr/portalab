vec2 c = floor(((gl_FragCoord.xy - 0.5 * u_res) / u_res.y) * 90.0) / 90.0;
  // An epic card turned: pixel rings exploding in bursts round it, 8-bit stars shooting out, the screen
  // flashing in colours (u_age: seconds, 2.2 s).
  float age = u_age;
  float fade = smoothstep(2.2, 1.6, age) * smoothstep(0.0, 0.1, age);
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float s = age - fk * 0.35;
    float rr = length(c * vec2(1.0, 0.85));
    float ring = step(abs(rr - s * 0.45), 0.012) * step(0.0, s) * step(s, 1.2);
    vec3 col = fk < 0.5 ? vec3(1.0, 0.3, 0.5) : fk < 1.5 ? vec3(1.0, 0.85, 0.2) : vec3(0.3, 0.8, 1.0);
    o = over(o, col, ring * fade);
  }
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float ang = fk / 16.0 * 6.2832;
    vec2 at = floor(vec2(cos(ang), sin(ang)) * (0.12 + age * 0.35) * 90.0) / 90.0;
    vec2 q = abs(c - at) * 90.0;
    float star = step(q.x + q.y, 1.6) + step(q.x, 0.1) * step(q.y, 3.1) + step(q.y, 0.1) * step(q.x, 3.1);
    o = over(o, mix(vec3(1.0, 1.0, 0.6), vec3(1.0, 0.5, 0.9), mod(fk, 2.0)), clamp(star, 0.0, 1.0) * fade);
  }
  float flash = step(0.5, fract(age * 8.0)) * smoothstep(0.5, 0.0, age);
  o = over(o, vec3(1.0), flash * 0.25 * step(length(c), 0.45));
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
