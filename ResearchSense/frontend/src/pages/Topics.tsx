import { useQuery } from "@tanstack/react-query";

import { fetchTopics } from "../api/topics";
import { PageHeader } from "../components/PageHeader";
import { TopicCard } from "../components/TopicCard";
import { Loader, ErrorState } from "../components/StateViews";
import styles from "./Topics.module.css";

export default function Topics() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });

  return (
    <>
      <PageHeader
        eyebrow="Fields of inquiry"
        title="Research areas"
        description="The topics that organise research at Bahria University E-8. Select an area to see its publications."
      />
      <div className={`container ${styles.body}`}>
        {isLoading && <Loader />}
        {isError && <ErrorState />}
        {data && (
          <div className={styles.grid}>
            {data.map((t) => (
              <TopicCard key={t.topic_id} topic={t} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
