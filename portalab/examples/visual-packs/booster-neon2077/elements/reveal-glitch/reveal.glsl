// A rare card turned: the picture breaking up round it — shifted slices, colours split into pink and cyan,
  // tearing scanlines (u_age: seconds, 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.2, age) * smoothstep(0.0, 0.1, age);
  float row = floor(c.y * 40.0);
  float shift = (hash(vec2(row, floor(age * 16.0))) - 0.5) * 0.12 * step(0.6, hash(vec2(row, 3.0 + floor(age * 16.0))));
  vec2 e = (c + vec2(shift, 0.0)) / vec2(0.3, 0.4);
  float frame = smoothstep(0.08, 0.0, abs(max(abs(e.x), abs(e.y)) - 1.0));
  vec2 e1 = (c + vec2(shift + 0.012, 0.0)) / vec2(0.3, 0.4);
  vec2 e2 = (c + vec2(shift - 0.012, 0.0)) / vec2(0.3, 0.4);
  o = over(o, vec3(1.0, 0.0, 0.4), smoothstep(0.08, 0.0, abs(max(abs(e1.x), abs(e1.y)) - 1.0)) * fade);
  o = over(o, vec3(0.0, 0.95, 1.0), smoothstep(0.08, 0.0, abs(max(abs(e2.x), abs(e2.y)) - 1.0)) * fade);
  o = over(o, vec3(1.0), frame * 0.6 * fade);
  float tear = step(0.85, hash(vec2(row, floor(age * 22.0)))) * smoothstep(0.55, 0.3, abs(c.y)) * smoothstep(0.2, 0.35, abs(c.x) + abs(shift));
  o = over(o, mix(vec3(1.0, 0.1, 0.5), vec3(0.1, 1.0, 1.0), hash(vec2(row, 7.0))), tear * 0.6 * fade);
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
