<script lang="ts">
  // One quiet line when the topic data did not load. Owner: P2.
  import * as copy from '../copy'
  import type { Failure } from '../model'
  import { TID } from '../testids'

  let { failure }: { failure: Failure } = $props()

  const text = $derived(
    failure.status === 0 && failure.code === 'network'
      ? copy.ERR.network
      : failure.code === 'topic_not_found'
        ? copy.ERR.topicNotFound
        : failure.status === 404
          ? copy.ERR.notFound
          : failure.status === 429 && failure.retryAfterS
            ? copy.ERR.rateLimited(failure.retryAfterS)
            : copy.ERR.generic,
  )
</script>

<p class="err sec" role="alert" data-testid={TID.stateError}>{text}</p>

<style>
  .err { padding: 40px 0 48px; }
</style>
