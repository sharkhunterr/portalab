// An epic card turned: shiny baubles springing out around it, bouncing, catching the light
  // (u_age: seconds, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.6, age) * smoothstep(0.0, 0.15, age);
  for (int k = 0; k < 10; k++) {
    float fk = float(k);
    float ang = fk / 10.0 * 6.2832 + 0.3;
    float reach = (0.25 + 0.12 * hash(vec2(fk, 1.0))) * (1.0 - exp(-age * 4.0));
    float hop = abs(sin(age * 5.0 + fk)) * 0.025 * exp(-age);
    vec2 b = vec2(cos(ang), sin(ang)) * reach + vec2(0.0, hop);
    float size = 0.03 + 0.015 * hash(vec2(fk, 2.0));
    float dd = length(c - b);
    vec3 col = fk - 3.0 * floor(fk / 3.0) < 0.5 ? vec3(0.9, 0.15, 0.2) : fk - 3.0 * floor(fk / 3.0) < 1.5 ? vec3(0.95, 0.75, 0.2) : vec3(0.15, 0.6, 0.35);
    float body = smoothstep(size, size * 0.92, dd);
    float glint = exp(-length(c - b - vec2(-0.3, 0.35) * size) * 220.0);
    o = over(o, col * (0.6 + 0.6 * smoothstep(size, 0.0, length(c - b - vec2(-0.3, 0.3) * size))), body * fade);
    o = over(o, vec3(1.0), glint * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
