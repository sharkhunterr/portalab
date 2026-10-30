// Impact — a rare card turned (u_age: seconds, 1.8 s): behind it a burst of pink rays shoots out and falls
  // back, a white and pink shockwave rolls away, speed lines streak out from it.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float a = atan(c.y, c.x);
  float fade = smoothstep(0.0, 0.12, age) * smoothstep(1.8, 1.2, age);
  // the burst: jagged rays, longest just after the turn
  float n = 20.0;
  float s = a / 6.2832 * n;
  float id = floor(s);
  float reach = (0.46 + 0.42 * hash(vec2(id, 5.0))) * smoothstep(0.0, 0.35, age) * (1.0 - 0.4 * smoothstep(0.5, 1.6, age));
  float halfw = 0.4 * clamp(1.0 - r / max(reach, 0.001), 0.0, 1.0);
  o = over(o, vec3(1.0, 0.16, 0.55), smoothstep(halfw, halfw - 0.07, abs(fract(s) - 0.5)) * fade);
  // white rays inside, shorter
  float inner = halfw * 0.5 * step(0.5, hash(vec2(id, 6.0)));
  o = over(o, vec3(1.0, 0.95, 1.0), smoothstep(inner, inner - 0.05, abs(fract(s) - 0.5)) * fade * 0.85);
  // the shockwave
  float wave = 0.12 + age * 0.55;
  o = over(o, vec3(1.0, 0.85, 0.95), smoothstep(0.012, 0.0, abs(r - wave)) * smoothstep(1.1, 0.3, age));
  o = over(o, vec3(1.0, 0.25, 0.6), smoothstep(0.03, 0.0, abs(r - wave + 0.02)) * 0.5 * smoothstep(1.1, 0.3, age));
  // speed lines streaking outwards
  float lanes = a / 6.2832 * 48.0;
  float lid = floor(lanes);
  float lane = smoothstep(0.12, 0.0, abs(fract(lanes) - 0.5));
  float head = 0.15 + fract(age * (1.2 + hash(vec2(lid, 2.0))) + hash(vec2(lid, 3.0))) * 0.5;
  float streak = step(r, head) * step(head - 0.12, r) * (r - head + 0.12) / 0.12;
  o = over(o, vec3(1.0), lane * streak * step(0.6, hash(vec2(lid, 4.0))) * fade * 0.8);
  // its edges fade out: never the outline of its box
  vec2 edge = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edge));
