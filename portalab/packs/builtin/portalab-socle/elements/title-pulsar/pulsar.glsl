// Portalab — title/pulsar: the « pulsar » effect (spec 028, B2)
  vec2 e = vec2(p.x / max(ax, 0.001), p.y);
  float r = length(e);
  float spin = t * 2.2;
  vec2 dir = vec2(cos(spin), sin(spin));
  float across = abs(dot(e, vec2(-dir.y, dir.x)));
  float beam = exp(-across * mix(18.0, 5.0, clamp(r / 3.0, 0.0, 1.0))) * smoothstep(0.05, 0.4, r);
  float pulse = fract(t * 2.2 / 3.1416);
  float wave = smoothstep(0.05, 0.0, abs(r - pulse * 2.6)) * (1.0 - pulse);
  vec3 body = mix(vec3(0.03, 0.02, 0.1), vec3(0.15, 0.08, 0.35), smoothstep(1.0, 0.0, r));
  float field = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float k = 0.35 + 0.25 * fi;
    vec2 m = mat2(cos(spin * 0.5), -sin(spin * 0.5), sin(spin * 0.5), cos(spin * 0.5)) * e;
    float dip = abs(length(vec2(abs(m.x) - k, m.y)) - k);
    field += smoothstep(0.03, 0.0, dip) * (0.5 - fi * 0.12);
  }
  body += vec3(0.55, 0.45, 1.0) * field * 0.6;
  body += vec3(0.75, 0.85, 1.0) * beam * 0.9;
  body += vec3(1.0) * exp(-r * 9.0) * (0.85 + 0.15 * sin(t * 30.0));
  body += vec3(0.6, 0.5, 1.0) * smoothstep(-0.2, 0.0, d) * 0.45;
  o = over(o, vec3(0.7, 0.8, 1.0), beam * step(0.0, d) * 0.85);
  o = over(o, vec3(0.65, 0.55, 1.0), wave * 0.7 * step(0.0, d));
  o = over(o, vec3(0.5, 0.4, 1.0), exp(-max(d, 0.0) * 4.5) * 0.3 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
