// Chrome purple studs behind the art: each stud's dome reflecting a room (bands of light sliding over it as the
  // view drifts), deep shadows, a bright highlight; sparkles.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec2 g = c * 6.0 + 0.5;
  vec2 sf = fract(g) - 0.5;
  float sr = length(sf);
  float dome = smoothstep(0.32, 0.29, sr);
  vec3 n = normalize(vec3(sf * 2.2 * dome, 1.0));
  float env = 0.5 + 0.5 * sin(n.x * 6.0 + n.y * 3.0 + t * 0.9) * cos(n.y * 5.0 - t * 0.6);
  vec3 chrome = mix(vec3(0.18, 0.06, 0.32), vec3(0.85, 0.7, 1.0), env);
  chrome += vec3(1.0) * pow(max(dot(n, normalize(vec3(-0.5, 0.6, 0.6))), 0.0), 40.0) * 0.9;
  vec3 plate = mix(vec3(0.25, 0.1, 0.45), vec3(0.6, 0.45, 0.85), 0.5 + 0.5 * sin(c.y * 6.0 + t * 0.7));
  plate *= 1.0 - 0.4 * smoothstep(0.42, 0.3, length(sf - vec2(0.06, -0.07))) * (1.0 - dome);
  vec3 col = mix(plate, chrome, dome);
  col += vec3(1.0, 0.95, 1.0) * step(0.97, hash(floor(g) + floor(t * 3.0))) * dome * 0.6;
  o = vec4(col, 1.0);
