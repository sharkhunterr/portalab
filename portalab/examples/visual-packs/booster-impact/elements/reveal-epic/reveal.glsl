// Impact — an epic card turned (u_age: seconds, 2.4 s): two white brush slashes cross behind it in an X, a pink
  // burst blooms where they meet, sparks fly out and a crosshair lights up at its corner.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float a = atan(c.y, c.x);
  float fade = smoothstep(0.0, 0.1, age) * smoothstep(2.4, 1.7, age);
  // the pink burst
  float s = a / 6.2832 * 26.0;
  float id = floor(s);
  float reach = (0.45 + 0.45 * hash(vec2(id, 7.0))) * smoothstep(0.15, 0.5, age);
  float halfw = 0.42 * clamp(1.0 - r / max(reach, 0.001), 0.0, 1.0);
  o = over(o, vec3(1.0, 0.13, 0.52), smoothstep(halfw, halfw - 0.06, abs(fract(s) - 0.5)) * fade);
  o = over(o, vec3(1.0, 0.8, 0.95), exp(-r * 9.0) * fade * 0.8);
  // two brush slashes in an X, each drawn fast across, ragged, edged with pink, then fading
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float since = age - fk * 0.14;
    float ang = mix(0.7, -0.7, fk);
    vec2 q = vec2(c.x * cos(ang) + c.y * sin(ang), -c.x * sin(ang) + c.y * cos(ang));
    float front = since * 5.0 - 0.7;
    float drawn = step(q.x, front) * step(0.0, since);
    float thick = 0.06 * (1.0 - 0.6 * smoothstep(-0.6, 0.6, q.x)) * (0.7 + 0.6 * noise(vec2(q.x * 10.0, fk * 5.0)));
    float edge = thick + 0.015 * (noise(vec2(q.x * 45.0, fk * 9.0)) - 0.5);
    float stroke = smoothstep(edge, edge - 0.008, abs(q.y));
    float rim = smoothstep(edge + 0.016, edge, abs(q.y)) - stroke;
    float life = drawn * smoothstep(1.3, 0.6, since);
    o = over(o, vec3(1.0, 0.2, 0.6), clamp(rim, 0.0, 1.0) * life);
    o = over(o, vec3(1.0), stroke * life);
  }
  // sparks flying out
  for (int k = 0; k < 20; k++) {
    float fk = float(k);
    float dir = hash(vec2(fk, 1.0)) * 6.2832;
    float speed = 0.25 + 0.35 * hash(vec2(fk, 2.0));
    vec2 sp = vec2(cos(dir), sin(dir)) * (0.1 + age * speed);
    vec2 dd = c - sp;
    float star = exp(-abs(dd.x) * 900.0) * exp(-abs(dd.y) * 60.0) + exp(-abs(dd.y) * 900.0) * exp(-abs(dd.x) * 60.0);
    o = over(o, mix(vec3(1.0), vec3(1.0, 0.4, 0.7), step(0.5, hash(vec2(fk, 3.0)))), clamp(star + exp(-length(dd) * 300.0), 0.0, 1.0) * fade * step(0.2, age));
  }
  // a crosshair lighting up at its top-right corner
  vec2 cp = c - vec2(0.24, 0.3);
  float cr = length(cp);
  float lit = smoothstep(0.5, 0.7, age) * fade;
  o = over(o, vec3(1.0, 0.3, 0.6), smoothstep(0.004, 0.0, abs(cr - 0.05)) * lit);
  o = over(o, vec3(1.0), (exp(-abs(cp.x) * 700.0) * step(abs(cp.y), 0.08) + exp(-abs(cp.y) * 700.0) * step(abs(cp.x), 0.08)) * step(0.02, cr) * lit);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
