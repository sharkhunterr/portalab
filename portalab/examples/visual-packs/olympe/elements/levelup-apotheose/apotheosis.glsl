// Apotheosis — a level-up over the whole stage (gl_FragCoord, u_res, u_age): clouds parting from the middle,
  // a column of light coming down, golden feathers falling, then a laurel wreath closing round the level.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.5, tl) * smoothstep(6.8, 5.6, tl);
  float part = smoothstep(0.3, 2.0, tl);
  float cl = fbm(vec2(c.x * 3.0, c.y * 4.0 + tl * 0.2)) + abs(c.x) * 1.5 - part * 0.9;
  o = over(o, vec3(1.0, 0.98, 0.95), smoothstep(0.3, 0.55, cl) * 0.9 * fade);
  float column = smoothstep(0.22 * part, 0.0, abs(c.x)) * smoothstep(-0.6, 0.6, c.y);
  o = over(o, vec3(1.0, 0.92, 0.65), column * 0.6 * fade);
  o = over(o, vec3(1.0, 0.96, 0.8), pow(0.5 + 0.5 * sin(atan(c.y - 0.6, c.x) * 18.0 + tl * 0.4), 6.0) * smoothstep(1.0, 0.2, length(c - vec2(0.0, 0.6))) * 0.3 * part * fade);
  for (int k = 0; k < 14; k++) {
    float fk = float(k);
    float fall = fract(tl * 0.12 + hash(vec2(fk, 1.0)));
    vec2 at = vec2((hash(vec2(fk, 2.0)) - 0.5) * 1.2 + 0.08 * sin(fall * 10.0 + fk), 0.6 - fall * 1.3);
    float ang = 0.6 * sin(fall * 8.0 + fk);
    vec2 q = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * (c - at);
    float feather = smoothstep(1.0, 0.8, length(q / vec2(0.012, 0.04)));
    o = over(o, vec3(0.95, 0.78, 0.35), feather * 0.85 * smoothstep(0.5, 1.2, tl) * fade);
  }
  float wreath = smoothstep(2.0, 2.8, tl);
  float r = length(c);
  float a = atan(c.y, c.x);
  float side = step(-1.2, a) * step(a, 4.4) * step(0.35, abs(a - 1.5708));
  float leaves = step(0.5, fract(a * 5.0)) * smoothstep(0.03, 0.0, abs(r - 0.22 - 0.015 * sin(a * 31.0)));
  o = over(o, vec3(0.8, 0.62, 0.15), leaves * side * wreath * fade);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
