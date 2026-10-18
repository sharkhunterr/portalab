vec2 c = floor(((gl_FragCoord.xy - 0.5 * u_res) / u_res.y) * 90.0) / 90.0;
  // Rétro — power on (u_age: seconds, 2.6 s): the screen off, then at 1.4 s a white line opens across it
  // and spreads into a flash, the colours bleeding back; a burst of pixel coins and stars thrown up and falling.
  float age = u_age;
  float on = smoothstep(1.35, 1.4, age);
  float open = smoothstep(1.4, 1.65, age);
  float line = step(abs(c.y), 0.004 + open * 0.5) * step(abs(c.x), 0.05 + smoothstep(1.35, 1.45, age) * 0.6);
  o = over(o, vec3(1.0), line * on * smoothstep(1.95, 1.65, age));
  if (age > 1.5) {
    float s = age - 1.5;
    float fade = smoothstep(1.1, 0.6, s);
    for (int k = 0; k < 30; k++) {
      float fk = float(k);
      float ang = 1.5708 + (hash(vec2(fk, 1.0)) - 0.5) * 2.6;
      float speed = 0.5 + 0.5 * hash(vec2(fk, 2.0));
      vec2 at = floor((vec2(cos(ang), sin(ang)) * speed * s * 1.1 + vec2(0.0, -0.8 * s * s)) * 90.0) / 90.0;
      vec2 q = abs(c - at) * 90.0;
      float coin = step(q.x, 1.1 * abs(cos(s * 10.0 + fk))) * step(q.y, 1.6);
      float star = step(q.x + q.y, 1.6);
      float kind = step(0.5, hash(vec2(fk, 3.0)));
      o = over(o, mix(vec3(1.0, 0.85, 0.2), vec3(0.6, 0.9, 1.0), kind), mix(coin, star, kind) * fade);
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
