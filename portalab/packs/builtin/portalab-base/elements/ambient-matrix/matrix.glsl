// Portalab — ambient/matrix: the « matrix » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float columns = floor(u_res.x / u_res.y * 34.0);
  vec2 cellSize = vec2(1.0 / columns, 1.0 / 26.0);
  vec2 cell = floor(uv / cellSize);
  vec2 inCell = fract(uv / cellSize);
  float speed = 0.35 + hash(vec2(cell.x, 1.0)) * 0.9;
  float offset = hash(vec2(cell.x, 2.0)) * 40.0;
  float head = fract(t * speed * 0.08 + offset / 40.0);       // where the column's head is (0..1, falling)
  float row = 1.0 - (cell.y + 0.5) * cellSize.y;               // 0 at the top
  float behind = head - row;                                   // how far above the head this cell is
  float trail = behind >= 0.0 ? exp(-behind * 7.0) : 0.0;
  float second = fract(head + 0.5) - row;                      // a second, fainter drop per column
  trail = max(trail, second >= 0.0 ? exp(-second * 10.0) * 0.45 : 0.0);
  // the glyph: a random 5x7 dot pattern, changing now and then
  vec2 g = floor(vec2(inCell.x * 5.0, inCell.y * 7.0));
  float glyphSeed = floor(t * (1.5 + hash(cell) * 4.0));
  float bit = step(0.5, hash(cell * 7.13 + g * 1.31 + glyphSeed));
  vec2 dot_ = fract(vec2(inCell.x * 5.0, inCell.y * 7.0)) - 0.5;
  float lit = bit * smoothstep(0.5, 0.25, max(abs(dot_.x), abs(dot_.y)));
  lit *= step(0.12, inCell.x) * step(inCell.x, 0.88) * step(0.06, inCell.y) * step(inCell.y, 0.94);
  float isHead = smoothstep(cellSize.y * 1.2, 0.0, abs(behind));
  vec3 col = mix(vec3(0.05, 0.85, 0.35), vec3(0.85, 1.0, 0.9), isHead);
  float a = lit * trail * 0.9;
  float glow = trail * 0.06;
  gl_FragColor = vec4(col * a + vec3(0.0, 0.5, 0.2) * glow, max(a, glow));
}