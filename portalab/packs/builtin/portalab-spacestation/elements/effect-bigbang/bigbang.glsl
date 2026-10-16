// Portalab — effect/bigbang: the « bigbang » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c);
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(6.6, 5.4, tl);
  float point = smoothstep(0.0, 0.5, tl) * step(tl, 0.8);
  o = over(o, vec3(1.0), exp(-r * mix(120.0, 40.0, point)) * point);
  float bang = max(tl - 0.8, 0.0);
  float after = step(0.8, tl);
  float flash = exp(-bang * 6.0) * after;
  float size = 1.5 * (1.0 - exp(-bang * 1.0)) + 0.001;
  float cool = clamp(bang / 3.2, 0.0, 1.0);
  float x = r / size;
  vec2 w = vec2(fbm(c * 3.0 + bang * 0.2), fbm(c * 3.0 + 5.0 - bang * 0.15));
  float churn = fbm(c * 5.0 + w * 1.5 - vec2(0.0, bang * 0.3));
  // the fireball: white-hot at its heart, orange towards its edge, cooling to violet — never opaque
  vec3 hot = mix(vec3(1.0, 0.97, 0.88), vec3(1.0, 0.6, 0.18), smoothstep(0.0, 0.9, x + cool * 0.6));
  hot = mix(hot, vec3(0.55, 0.2, 0.7), smoothstep(0.35, 1.0, cool));
  float ball = smoothstep(1.0, 0.55, x) * (0.35 + 0.65 * churn) * (0.85 - 0.6 * cool) * exp(-max(bang - 1.4, 0.0) * 1.3) * after;
  o = over(o, hot, ball * fade);
  float shell = exp(-abs(x - 1.0) * 14.0) * exp(-bang * 0.7) * after;
  o = over(o, vec3(1.0, 0.85, 0.65), shell * 0.8 * fade);
  // the cosmic web as it cools: thin bright filaments only
  // the cosmic web as it cools: thin threads where the matter gathers, brighter at their knots
  float level = fbm(c * 3.5 + w * 2.0);
  float thread = smoothstep(0.018, 0.0, abs(level - 0.5)) + 0.6 * smoothstep(0.012, 0.0, abs(fbm(c * 7.0 + w * 3.0) - 0.5));
  float knots = smoothstep(0.62, 0.8, fbm(c * 6.0 - w)) * thread;
  float filaments = thread * smoothstep(0.35, 0.9, cool);
  o = over(o, vec3(0.65, 0.72, 1.0), filaments * 0.55 * fade);
  o = over(o, vec3(1.0, 0.9, 0.8), knots * smoothstep(0.35, 0.9, cool) * 0.6 * fade);
  o = over(o, vec3(1.0, 0.98, 0.95), flash * exp(-r * 1.2));
  for (int i = 0; i < 16; i++) {
    float fi = float(i);
    float a = hash(vec2(fi, 111.0)) * 6.2832;
    vec2 at = vec2(cos(a), sin(a)) * (0.15 + 0.75 * hash(vec2(fi, 112.0))) * (1.0 - exp(-bang * 0.6));
    vec2 g = c - at;
    float gr = length(g) + 0.0001;
    float arms = sin(atan(g.y, g.x) * 2.0 - log(gr) * 3.0 + tl * 2.0 + fi);
    float gal = exp(-gr * 70.0) + smoothstep(0.04, 0.0, gr) * (0.5 + 0.5 * arms) * 0.6;
    vec3 gc = mix(vec3(0.8, 0.6, 1.0), vec3(1.0, 0.85, 0.65), hash(vec2(fi, 113.0)));
    o = over(o, gc, gal * smoothstep(1.6, 2.6, tl) * fade);
  }
