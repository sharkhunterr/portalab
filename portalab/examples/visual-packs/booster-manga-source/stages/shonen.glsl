// Shōnen — the booster stage: a rocky plateau under a storm — heavy clouds rolling, lightning flickering far
  // off, the horizon's ridge, rocks floating and bobbing, dust blown across (a stage: gl_FragCoord, u_res, t;
  // into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.05, 0.04, 0.08), vec3(0.18, 0.12, 0.16), smoothstep(0.5, -0.3, c.y)), 1.0);
  // clouds rolling, lit from below now and then by lightning
  vec2 q = c * vec2(1.4, 2.2) + vec2(t * 0.02, 0.0);
  float cloud = fbm(q * 1.3 + fbm(q * 1.6 + t * 0.03) * 1.5) * 1.25;
  float strike = pow(max(0.0, sin(t * 0.7) * sin(t * 2.3 + 1.0)), 18.0);
  float lit = smoothstep(0.3, 0.75, cloud);
  o = over(o, mix(vec3(0.16, 0.12, 0.2), vec3(0.85, 0.8, 1.0), strike), lit * smoothstep(-0.2, 0.3, c.y) * 0.9);
  o = over(o, mix(vec3(0.45, 0.32, 0.42), vec3(1.0, 0.95, 1.0), strike), smoothstep(0.55, 0.85, cloud) * smoothstep(-0.2, 0.3, c.y) * 0.55);
  o = over(o, vec3(0.75, 0.3, 0.1), smoothstep(0.35, 0.7, cloud) * smoothstep(0.1, -0.2, c.y) * 0.35);
  // the bolt itself, far off
  float bx = c.x - (fract(floor(t * 0.7 / 6.283) * 0.37) - 0.5) * asp * 0.8;
  float zig = abs(bx + 0.03 * sin(c.y * 40.0)) ;
  o = over(o, vec3(0.9, 0.9, 1.0), smoothstep(0.006, 0.0, zig) * step(0.05, c.y) * strike);
  // the plateau: a ridge, then the ground, a warm glow at the horizon
  float ridge = -0.18 + 0.04 * sin(c.x * 6.0) + 0.02 * sin(c.x * 17.0 + 1.0);
  o = over(o, vec3(0.9, 0.42, 0.12), exp(-abs(c.y - ridge) * 30.0) * 0.25);
  float ground = smoothstep(ridge + 0.005, ridge - 0.005, c.y);
  o = over(o, mix(vec3(0.1, 0.08, 0.1), vec3(0.2, 0.16, 0.16), smoothstep(-0.5, ridge, c.y)), ground);
  o = over(o, vec3(0.03, 0.02, 0.04), ground * smoothstep(0.85, 0.0, fbm(c * 9.0)) * 0.5);
  // rocks floating and bobbing
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    vec2 rp = vec2((hash(vec2(fk, 1.0)) - 0.5) * asp * 0.95, -0.05 + 0.35 * hash(vec2(fk, 2.0)) + 0.02 * sin(t * (0.6 + hash(vec2(fk, 3.0))) + fk));
    float size = 0.015 + 0.03 * hash(vec2(fk, 4.0));
    vec2 rd = (c - rp) / size;
    float rock = length(rd * vec2(1.0, 1.4)) + 0.25 * fbm(rd * 1.5 + fk);
    o = over(o, mix(vec3(0.12, 0.1, 0.12), vec3(0.4, 0.35, 0.34), smoothstep(0.4, -0.6, rd.y)), smoothstep(1.05, 0.95, rock));
    o = over(o, vec3(1.0, 0.5, 0.15), smoothstep(1.4, 1.0, rock) * (1.0 - smoothstep(1.0, 0.95, rock)) * 0.25);
  }
  // dust blown across
  vec2 dq = c * vec2(3.0, 10.0) + vec2(t * 0.25, 0.0);
  o = over(o, vec3(0.7, 0.55, 0.4), smoothstep(0.6, 0.9, fbm(dq)) * smoothstep(0.0, -0.4, c.y) * 0.18);
