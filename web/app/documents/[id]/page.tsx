import { MetadataReview } from "@/components/metadata-review";

export default async function DocumentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MetadataReview id={id} />;
}
