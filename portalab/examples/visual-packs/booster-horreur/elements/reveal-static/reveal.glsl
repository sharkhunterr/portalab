// A rare card turned: the picture breaking up round it — screen snow, lines tearing, a roll
  // (u_age: seconds, 1.6 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.6, 1.0, age) * smoothstep(0.0, 0.08, age);
  float row = floor(gl_FragCoord.y / 3.0);
  float tear = step(0.88, hash(vec2(row, floor(age * 20.0)))) * 0.6;
  float snow = hash(gl_FragCoord.xy * 0.5 + floor(age * 30.0));
  float roll = smoothstep(0.03, 0.0, abs(fract(c.y * 0.8 - age * 1.5) - 0.5));
  float ring = smoothstep(0.75, 0.25, length(c * vec2(0.9, 0.75))) * smoothstep(0.12, 0.3, length(c * vec2(0.9, 0.75)));
  o = over(o, vec3(snow), ring * (0.35 + tear) * fade);
  o = over(o, vec3(0.9, 1.0, 1.0), roll * ring * 0.5 * fade);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
