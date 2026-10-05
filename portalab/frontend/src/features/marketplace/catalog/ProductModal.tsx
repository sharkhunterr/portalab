import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { type Product, useProduct } from "../api";
import { ProductSheet, PurchaseBar } from "../product/ProductSheet";

/**
 * A product opened from the shop (027): its sheet — pre-rendering, rarity, type, description, pack
 * contents, price, copies left, level, limit, refund policy, conditions — with « Close » and « Buy » in a
 * footer that stays in view. Opened without leaving the shelves.
 */
export function ProductModal({ product, onClose }: { product: Product; onClose: () => void }) {
  const t = useT();
  const full = useProduct(product.key);
  const data = full.data ?? product;
  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      size="lg"
      title={data.name}
      closeLabel={t("marketplace:purchase.close")}
      trigger={<span hidden />}
      footer={<PurchaseBar product={data} />}
    >
      <ProductSheet product={data} />
    </Dialog>
  );
}
