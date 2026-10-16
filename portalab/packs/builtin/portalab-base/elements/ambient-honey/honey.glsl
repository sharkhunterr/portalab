// Portalab — ambient/honey: the « honey » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.6, 0.15), 0.05);
  vec3 honey = vec3(0.95, 0.58, 0.1);
  vec3 deep = vec3(0.6, 0.28, 0.04);
  // the edge along the top, drops hanging from it
  float top = 0.95 - 0.015 * noise(vec2(p.x * 4.0, t * 0.1)) - 0.01 * sin(p.x * 3.0 + t * 0.2);
  float k = 9.0;
  float col_ = floor(p.x * k);
  float fx = fract(p.x * k) - 0.5;
  float h = hash(vec2(col_, 1.0));
  float period = 9.0 + 8.0 * h;
  float ph = fract(t / period + h);
  float len = 0.04 + 0.28 * smoothstep(0.0, 0.85, ph) * h;
  float hang = top - len;
  float strand = step(abs(fx), 0.05 + 0.12 * smoothstep(hang + 0.1, top, p.y)) * step(hang, p.y) * step(p.y, top + 0.01) * step(0.35, h);
  float bulb = smoothstep(1.0, 0.85, length(vec2(fx / 0.16, (p.y - hang) / 0.022))) * step(0.35, h) * step(ph, 0.85);
  // the drop letting go, falling
  float fall = (ph - 0.85) / 0.15;
  float dropY = hang - fall * fall * 1.1;
  float drop = smoothstep(1.0, 0.8, length(vec2(fx / 0.14, (p.y - dropY) / 0.024))) * step(0.85, ph) * step(0.35, h);
  float edge = step(top, p.y);
  float mass = clamp(edge + strand + bulb + drop, 0.0, 1.0);
  float shine = smoothstep(0.03, 0.0, abs(fx + 0.04)) * clamp(strand + bulb, 0.0, 1.0) + smoothstep(0.006, 0.0, abs(p.y - top - 0.012)) * edge;
  o = over(o, mix(deep, honey, 0.5 + 0.5 * (p.y - hang) / max(top - hang, 0.01)), mass * 0.85);
  o = over(o, vec3(1.0, 0.92, 0.7), shine * 0.6);
  // the pool at the bottom, slowly rippling, glinting
  float level = 0.08 + 0.008 * sin(p.x * 5.0 + t * 0.4) + 0.005 * sin(p.x * 11.0 - t * 0.3);
  float pool = step(p.y, level);
  float glint = 1.0 - abs(2.0 * fbm(vec2(p.x * 8.0 + t * 0.05, p.y * 30.0)) - 1.0);
  o = over(o, mix(deep, honey, smoothstep(0.0, level, p.y)), pool * 0.85);
  o = over(o, vec3(1.0, 0.9, 0.6), pool * smoothstep(0.95, 0.995, glint) * 0.3);
  o = over(o, vec3(1.0, 0.92, 0.7), smoothstep(0.004, 0.0, abs(p.y - level)) * 0.6);
  gl_FragColor = o;
}