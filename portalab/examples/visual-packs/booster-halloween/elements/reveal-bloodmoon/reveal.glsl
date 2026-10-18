// A legendary card turned: a blood eclipse — the moon turning red behind it, its corona of fire, red lightning
  // branching out, a demon's face looming out of the dark above (horns, burning eyes), an ember storm and a
  // shockwave (u_age: seconds, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.2, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  // the demon, looming above: horns, burning eyes, a grin of fire — fading in out of the dark
  float loom = smoothstep(0.3, 1.2, age) * fade;
  vec2 dq = (c - vec2(0.0, 0.3)) * vec2(0.62, 0.72);
  float head = smoothstep(0.02, 0.0, length(dq * vec2(1.0, 1.25)) - 0.36);
  float hornL = smoothstep(0.01, 0.0, abs(dq.x + 0.25 + (dq.y - 0.2) * (0.3 + dq.y)) - 0.05 * (0.6 - dq.y)) * step(0.15, dq.y) * step(dq.y, 0.55);
  float hornR = smoothstep(0.01, 0.0, abs(dq.x - 0.25 - (dq.y - 0.2) * (0.3 + dq.y)) - 0.05 * (0.6 - dq.y)) * step(0.15, dq.y) * step(dq.y, 0.55);
  // soft toward the layer's sides and top: never its box
  float keep = smoothstep(0.34, 0.16, abs(c.x)) * smoothstep(0.5, 0.36, c.y);
  o = over(o, vec3(0.08, 0.0, 0.0), clamp(head + hornL + hornR, 0.0, 1.0) * 0.8 * loom * keep);
  float eyes = smoothstep(0.035, 0.012, length((dq - vec2(-0.12, 0.08)) * vec2(1.0, 2.2))) + smoothstep(0.035, 0.012, length((dq - vec2(0.12, 0.08)) * vec2(1.0, 2.2)));
  o = over(o, vec3(1.0, 0.55, 0.1), eyes * loom);
  o = over(o, vec3(1.0, 0.2, 0.0), (exp(-length(dq - vec2(-0.12, 0.08)) * 22.0) + exp(-length(dq - vec2(0.12, 0.08)) * 22.0)) * 0.5 * loom);
  // the eclipse behind the card: a dark disc, its corona of fire
  float corona = fbm(vec2(a * 5.0, r * 8.0 - age * 2.0));
  float rim = 0.22 + 0.05 * corona;
  o = over(o, vec3(1.0, 0.3, 0.05), smoothstep(rim + 0.12, rim, r) * smoothstep(rim - 0.03, rim, r) * fade);
  o = over(o, vec3(0.35, 0.0, 0.02), smoothstep(0.22, 0.21, r) * fade);
  // red lightning branching out from it
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float t0 = 0.3 + fk * 0.35;
    float on = step(t0, age) * step(age, t0 + 0.18);
    float dir = hash(vec2(fk, 4.0)) * 6.2832;
    float seg = floor(r * 16.0);
    float jag = dir + 0.25 * (hash(vec2(fk, seg)) - 0.5);
    float bolt = smoothstep(0.005, 0.0, abs(sin(a - jag)) * r) * step(0.2, r) * step(r, 0.75) * step(0.0, cos(a - jag));
    o = over(o, vec3(1.0, 0.35, 0.25), bolt * on);
    o = over(o, vec3(0.9, 0.1, 0.05), on * 0.18 * smoothstep(0.42, 0.12, r));
  }
  // the shockwave
  float front = 0.15 + age * 0.45;
  o = over(o, vec3(1.0, 0.45, 0.2), smoothstep(0.02, 0.0, abs(r - front)) * smoothstep(1.6, 0.8, age) * fade);
  // the ember storm, swirling up
  for (int k = 0; k < 36; k++) {
    float fk = float(k);
    float life = fract(age * (0.3 + 0.25 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 e = vec2((hash(vec2(fk, 3.0)) - 0.5) * 1.3 + 0.08 * sin(life * 8.0 + fk), -0.6 + life * 1.25);
    o = over(o, mix(vec3(1.0, 0.55, 0.15), vec3(1.0, 0.2, 0.05), hash(vec2(fk, 5.0))), exp(-length(c - e) * 170.0) * smoothstep(1.0, 0.7, life) * fade);
  }
  // its edges fade out, narrowly: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.08, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.08, min(edgeuv.y, 1.0 - edgeuv.y));
