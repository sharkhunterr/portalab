import { Avatar, type AvatarSize } from "../../design-system/components/Avatar";
import { FramedAvatar, StyledName } from "./profile/ProfileHero";

/**
 * issue 127: a member as the community shows them — their avatar in the frame they wear and their name in the
 * style they chose, as on their profile; an anonymous member keeps neither (no picture, no frame, no style).
 */
export interface MemberLook {
  frame?: string | null;
  name?: string | null;
}

export function MemberAvatar({
  id,
  name,
  look,
  size = "sm",
  anonymous = false,
  src,
}: {
  id: string;
  name: string;
  look?: MemberLook | null | undefined;
  size?: AvatarSize;
  anonymous?: boolean | null | undefined;
  /** the picture (default: the member's own; ``null`` none) */
  src?: string | null;
}) {
  if (anonymous) return <Avatar name={name} userId={id} src={null} size={size} decorative />;
  return (
    <FramedAvatar
      frame={look?.frame}
      name={name}
      userId={id}
      src={src === undefined ? `/api/v1/users/${id}/avatar` : src}
      size={size}
    />
  );
}

export function MemberName({ name, look }: { name: string; look?: MemberLook | null | undefined }) {
  return <StyledName name={name} style={look?.name} />;
}
