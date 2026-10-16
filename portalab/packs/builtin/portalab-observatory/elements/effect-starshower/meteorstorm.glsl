// Portalab — effect/starshower: the « meteorstorm » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float aspect = u_res.x / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.5, tl) * smoothstep(6.5, 5.3, tl);
  o = over(o, vec3(0.01, 0.01, 0.05), 0.5 * fade);
  vec2 radiant = vec2(-0.3 * aspect, 0.55);
  o = over(o, vec3(0.5, 0.6, 1.0), exp(-length(c - radiant) * 6.0) * 0.25 * fade);
  for (int i = 0; i < 64; i++) {
    float fi = float(i);
    float start = hash(vec2(fi, 101.0)) * 4.8;
    float life = (tl - start) / (0.5 + 0.6 * hash(vec2(fi, 102.0)));
    if (life < 0.0 || life > 1.4) continue;
    float a = -0.2 - hash(vec2(fi, 103.0)) * 2.4;
    vec2 way = vec2(cos(a), sin(a));
    vec2 from = radiant + way * (0.05 + 0.35 * hash(vec2(fi, 104.0)));
    vec2 head = from + way * life * (1.0 + 1.0 * hash(vec2(fi, 105.0)));
    vec2 rel = c - head;
    float along = dot(rel, -way);
    float across = abs(dot(rel, vec2(-way.y, way.x)));
    float big = step(0.85, hash(vec2(fi, 106.0)));
    float width = mix(0.0022, 0.0055, big) * (1.0 + along * 1.5);
    float trail = smoothstep(width, 0.0, across) * smoothstep(0.45 + big * 0.3, 0.0, along) * step(0.0, along);
    float burn = smoothstep(0.0, 0.12, life) * smoothstep(1.4, 0.85, life);
    vec3 col = mix(vec3(0.75, 0.85, 1.0), mix(vec3(0.5, 1.0, 0.6), vec3(1.0, 0.82, 0.45), hash(vec2(fi, 107.0))), big);
    o = over(o, col, trail * burn * fade);
    o = over(o, vec3(1.0), exp(-length(rel) * mix(200.0, 70.0, big)) * burn * fade);
    o = over(o, col, big * exp(-length(rel) * 8.0) * burn * 0.35 * fade);
  }
  vec2 sg = c * 40.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(1.0), step(0.986, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(tl * 4.0 + sh * 30.0)) * 0.8 * fade);
