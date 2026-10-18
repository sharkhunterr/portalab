// An epic card turned: a hexagonal grid spreading round it, data streams running along it in pink and cyan, a
  // yellow wave crossing it (u_age: seconds, 2.4 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.4, 1.7, age) * smoothstep(0.0, 0.2, age);
  float r = length(c);
  vec2 h = c * 22.0;
  vec2 hr = vec2(h.x + h.y * 0.577, h.y * 1.155);
  vec2 hf = fract(hr) - 0.5;
  float grid = smoothstep(0.41, 0.47, max(abs(hf.x), abs(hf.y)));
  float spread = smoothstep(age * 0.5 + 0.05, age * 0.5 - 0.05, r);
  o = over(o, vec3(0.1, 0.8, 1.0), grid * spread * 0.55 * fade);
  float cellOn = step(0.8, hash(floor(hr) + floor(age * 6.0)));
  o = over(o, mix(vec3(1.0, 0.1, 0.6), vec3(0.1, 1.0, 1.0), hash(floor(hr))), cellOn * spread * smoothstep(0.45, 0.2, max(abs(hf.x), abs(hf.y))) * 0.4 * fade);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float ang = fk * 0.785 + 0.2;
    vec2 dir = vec2(cos(ang), sin(ang));
    float along = dot(c, dir);
    float across = abs(dot(c, vec2(-dir.y, dir.x)));
    float packet = smoothstep(0.03, 0.0, abs(fract(along * 4.0 - age * 3.0) - 0.5) - 0.1);
    o = over(o, mix(vec3(1.0, 0.1, 0.6), vec3(0.1, 1.0, 1.0), mod(fk, 2.0)), smoothstep(0.004, 0.0, across) * step(0.2, along) * packet * fade);
  }
  o = over(o, vec3(0.99, 0.93, 0.04), smoothstep(0.012, 0.0, abs(r - age * 0.35)) * smoothstep(1.6, 0.8, age) * fade);
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
