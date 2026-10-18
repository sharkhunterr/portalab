// A rare card turned: a hexagonal shield bubble lighting round it, shots striking it, ripples at each hit
  // (u_age: seconds, 2.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.0, 1.4, age) * smoothstep(0.0, 0.15, age);
  vec2 e = c / vec2(0.3, 0.4);
  float r = length(e);
  // the hexagon grid on the bubble
  vec2 h = c * 26.0;
  vec2 hr = vec2(h.x + h.y * 0.577, h.y * 1.155);
  vec2 hf = fract(hr) - 0.5;
  float hex = smoothstep(0.42, 0.48, max(abs(hf.x), abs(hf.y)));
  float shell = smoothstep(0.25, 0.0, abs(r - 1.0)) + 0.3 * smoothstep(1.0, 0.6, r);
  o = over(o, vec3(0.3, 0.9, 1.0), (hex * 0.5 + 0.2) * shell * smoothstep(1.1, 0.95, r) * fade);
  // shots striking it, a ripple from each impact
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float at = 0.25 + fk * 0.35;
    float s = age - at;
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 hit = vec2(cos(ang) * 0.3, sin(ang) * 0.4);
    vec2 from = hit * 3.0;
    vec2 shot = mix(from, hit, clamp((s + 0.15) / 0.15, 0.0, 1.0));
    o = over(o, vec3(1.0, 0.4, 0.3), exp(-length(c - shot) * 200.0) * step(-0.15, s) * step(s, 0.0) * fade);
    float ring = smoothstep(0.01, 0.0, abs(length(c - hit) - s * 0.25)) * step(0.0, s) * smoothstep(0.5, 0.0, s);
    o = over(o, vec3(0.7, 1.0, 1.0), (ring + exp(-length(c - hit) * 40.0) * smoothstep(0.3, 0.0, s) * step(0.0, s)) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
