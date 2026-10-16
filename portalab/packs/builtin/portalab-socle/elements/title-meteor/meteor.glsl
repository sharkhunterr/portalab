// Portalab — title/meteor: the « meteor » effect (spec 028, B2)
  vec3 sky = mix(vec3(0.02, 0.02, 0.08), vec3(0.08, 0.06, 0.2), smoothstep(-1.0, 1.0, p.y));
  vec2 sg = p * 12.0;
  float sh = hash(floor(sg));
  sky += vec3(0.9, 0.92, 1.0) * step(0.93, sh) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.5 + sh * 40.0));
  sky += vec3(0.5, 0.45, 1.0) * smoothstep(-0.2, 0.0, d) * 0.4;
  o = over(o, vec3(0.5, 0.45, 1.0), exp(-max(d, 0.0) * 4.5) * 0.22 * step(0.0, d));
  o = over(o, sky, smoothstep(0.03, -0.03, d));
  vec2 way = normalize(vec2(-1.0, -0.55));
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float period = 2.3 + fi * 0.7;
    float k = floor((t + fi * 1.3) / period);
    float life = fract((t + fi * 1.3) / period) * 1.6;
    vec2 from = vec2((0.2 + hash(vec2(k, fi + 71.0)) * 1.2) * max(ax, 1.0), 0.6 + hash(vec2(k, fi + 72.0)) * 0.9);
    vec2 head = from + way * life * (2.4 + ax);
    vec2 rel = p - head;
    float along = dot(rel, -way);
    float across = abs(dot(rel, vec2(-way.y, way.x)));
    float trail = smoothstep(0.03, 0.0, across) * smoothstep(0.9, 0.0, along) * step(0.0, along);
    float burn = smoothstep(0.0, 0.2, life) * smoothstep(1.6, 1.1, life);
    o = over(o, mix(vec3(0.6, 0.75, 1.0), vec3(1.0, 0.95, 0.85), smoothstep(0.4, 0.0, along)), trail * burn);
    o = over(o, vec3(1.0), exp(-length(rel) * 28.0) * burn);
  }
