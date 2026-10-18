// Olympus — the wrath of Zeus (u_age: seconds, 2.8 s): golden cracks spreading over the amphora; at 2.0 s a
  // thunderbolt strikes from above — a jagged bolt, a white flash, shards flying out, a ring of golden light.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float strike = 2.0;
  float grow = smoothstep(0.6, strike, age) * step(age, strike + 0.05);
  float crack = abs(noise(c * 18.0) - 0.5);
  o = over(o, vec3(1.0, 0.85, 0.4), smoothstep(0.03, 0.0, crack) * step(length(c * vec2(1.6, 1.0)), 0.32 * grow));
  float pre = exp(-abs(age - 1.6) * 20.0) * 0.4;
  float bolt = abs(c.x - 0.04 * sin(c.y * 25.0) - 0.06 * (noise(vec2(c.y * 9.0, 2.0)) - 0.5));
  float on = step(strike - 0.08, age) * smoothstep(strike + 0.3, strike, age);
  o = over(o, vec3(0.85, 0.92, 1.0), (smoothstep(0.008, 0.0, bolt) + smoothstep(0.05, 0.0, bolt) * 0.4) * step(0.0, c.y) * (on + pre));
  if (age > strike) {
    float s = age - strike;
    float fade = smoothstep(0.8, 0.45, s);
    float r = length(c);
    o = over(o, vec3(1.0, 0.98, 0.9), exp(-r * 4.0) * smoothstep(0.3, 0.0, s));
    o = over(o, vec3(1.0, 0.85, 0.45), smoothstep(0.02, 0.0, abs(r - s * 0.7)) * fade);
    for (int k = 0; k < 18; k++) {
      float fk = float(k);
      float ang = hash(vec2(fk, 1.0)) * 6.2832;
      vec2 at = vec2(cos(ang), sin(ang)) * s * (0.5 + 0.5 * hash(vec2(fk, 2.0))) + vec2(0.0, -0.4 * s * s);
      vec2 q = c - at;
      float sp = ang + s * 6.0;
      q = mat2(cos(sp), -sin(sp), sin(sp), cos(sp)) * q;
      float shardk = step(abs(q.x) + abs(q.y) * 0.6, 0.02);
      o = over(o, mix(vec3(0.55, 0.22, 0.08), vec3(0.85, 0.45, 0.2), step(0.0, q.y)), shardk * fade);
    }
  }
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
