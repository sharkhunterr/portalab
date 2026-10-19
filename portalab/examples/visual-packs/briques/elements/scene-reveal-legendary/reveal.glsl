// A legendary card turned: a tower of gold bricks rising behind it brick after brick, gold rays bursting from
  // it, three sprays of coloured studs exploding like fireworks, gold dust falling (u_age, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.3, age) * smoothstep(0.0, 0.12, age);
  float r = length(c);
  float a = atan(c.y, c.x);
  o = over(o, vec3(1.0, 0.85, 0.45), pow(0.5 + 0.5 * sin(a * 14.0 + age * 0.6), 6.0) * smoothstep(1.0, 0.2, r) * smoothstep(0.3, 0.8, age) * 0.55 * fade);
  o = over(o, vec3(1.0, 0.92, 0.6), exp(-r * 5.0) * 0.6 * fade);
  for (int k = 0; k < 2; k++) {
    float side = k == 0 ? -1.0 : 1.0;
    for (int j = 0; j < 10; j++) {
      float fj = float(j);
      float when = fj * 0.1;
      float since = age - when;
      float landY = -0.5 + fj * 0.07;
      float y = landY + max(0.0, 0.5 - since * since * 8.0) * step(since, 0.25);
      vec2 q = c - vec2(side * (0.4 + 0.015 * mod(fj, 2.0)), y);
      float body = step(abs(q.x), 0.07) * step(abs(q.y), 0.035);
      float studs = step(0.035, q.y) * step(q.y, 0.048) * step(abs(q.x), 0.07) * step(abs(fract(q.x / 0.035 + 0.5) - 0.5), 0.28);
      vec3 gold = vec3(0.95, 0.72, 0.2) * (0.75 + 0.35 * smoothstep(-0.035, 0.035, q.y)) + vec3(1.0, 0.95, 0.75) * exp(-abs(q.x + q.y - mod(age, 1.0) * 0.3) * 30.0) * 0.4;
      o = over(o, gold, clamp(body + studs, 0.0, 1.0) * step(0.0, since) * fade);
    }
  }
  for (int f = 0; f < 3; f++) {
    float ff = float(f);
    float when = 0.8 + ff * 0.55;
    float s = age - when;
    vec2 centre = vec2((ff - 1.0) * 0.35, 0.3 + 0.08 * mod(ff, 2.0));
    for (int k = 0; k < 16; k++) {
      float fk = float(k);
      float ang = fk / 16.0 * 6.2832;
      vec2 at = centre + vec2(cos(ang), sin(ang)) * s * 0.35 + vec2(0.0, -0.25 * s * s);
      vec3 sc = 0.5 + 0.5 * cos(6.2832 * (ff * 0.3 + fk / 16.0 + vec3(0.0, 0.33, 0.67)));
      o = over(o, sc, smoothstep(0.012, 0.008, length(c - at)) * step(0.0, s) * smoothstep(1.1, 0.4, s) * fade);
    }
  }
  for (int k = 0; k < 20; k++) {
    float fk = float(k);
    float fall = fract(age * 0.3 + hash(vec2(fk, 3.0)));
    vec2 at = vec2((hash(vec2(fk, 4.0)) - 0.5) * 1.2, 0.6 - fall * 1.2);
    o = over(o, vec3(1.0, 0.85, 0.4), exp(-length(c - at) * 400.0) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
