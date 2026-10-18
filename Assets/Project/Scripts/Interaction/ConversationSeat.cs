using System.Collections;
using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.InputSystem;
using UnityEngine.XR.Interaction.Toolkit.Locomotion;

namespace IAI.Interaction
{
    /// <summary>Virtual seating. Moves the XR origin once under a fade, never the tracked camera.</summary>
    public sealed class ConversationSeat : MonoBehaviour
    {
        public enum SeatState { Standing, Available, Entering, Seated, Leaving }
        public XROrigin origin;
        public Transform seatAnchor;
        public Transform exitAnchor;
        public SeatViewFade viewFade;
        [Min(.5f)] public float approachDistance = 1.35f;
        public float seatedEyeHeight = 1.2f;
        public float fadeSeconds = .28f;
        public float blackHoldSeconds = .12f;
        public UnityEvent onSeated = new UnityEvent();
        public UnityEvent onStanding = new UnityEvent();

        public SeatState State { get; private set; }
        public bool IsSeated => State == SeatState.Seated;
        public bool IsTransitioning => State == SeatState.Entering || State == SeatState.Leaving;
        public string Feedback { get; private set; }

        InputAction sitInput, leaveInput;
        LocomotionProvider[] providers;
        bool[] providerStates;
        CharacterController character;
        bool characterWasEnabled, locked;
        float standingOriginY, nextActionTime;
        Coroutine transition;

        void Awake()
        {
            providers = origin.GetComponentsInChildren<LocomotionProvider>(true);
            providerStates = new bool[providers.Length];
            character = origin.GetComponent<CharacterController>();
            sitInput = new InputAction("Sit", InputActionType.Button);
            sitInput.AddBinding("<XRController>{RightHand}/primaryButton");
            sitInput.AddBinding("<XRController>{LeftHand}/primaryButton");
            leaveInput = new InputAction("Leave seat", InputActionType.Button);
            leaveInput.AddBinding("<XRController>{RightHand}/secondaryButton");
            leaveInput.AddBinding("<XRController>{LeftHand}/secondaryButton");
#if UNITY_EDITOR
            sitInput.AddBinding("<Keyboard>/enter");
            leaveInput.AddBinding("<Keyboard>/backspace");
#endif
        }

        void OnEnable() { sitInput.Enable(); leaveInput.Enable(); }

        void Update()
        {
            if (!IsTransitioning && !IsSeated)
                State = CanEnter() ? SeatState.Available : SeatState.Standing;
            if (sitInput.WasPressedThisFrame()) TrySit();
            if (leaveInput.WasPressedThisFrame()) TryLeave();
        }

        public bool CanEnter()
        {
            if (!origin || !origin.Camera || !seatAnchor) return false;
            Vector3 delta = origin.Camera.transform.position - seatAnchor.position;
            if (Mathf.Abs(delta.y) > 2.5f) return false;
            delta.y = 0;
            // Exclude the far side of the desk and add hysteresis to prevent a flickering prompt.
            float range = approachDistance + (State == SeatState.Available ? .15f : 0f);
            if (delta.sqrMagnitude > range * range || Vector3.Dot(delta, seatAnchor.forward) > .3f)
                return false;
            Vector3 toward = seatAnchor.position + Vector3.up * seatedEyeHeight - origin.Camera.transform.position;
            return Vector3.Angle(origin.Camera.transform.forward, toward) < 75f;
        }

        public bool TrySit()
        {
            if (!isActiveAndEnabled || IsTransitioning || IsSeated || Time.unscaledTime < nextActionTime || !CanEnter())
                return false;
            Feedback = null;
            State = SeatState.Entering;
            LockLocomotion();
            transition = StartCoroutine(ChangeSeat(true, Vector3.zero));
            return true;
        }

        public bool TryLeave()
        {
            if (!isActiveAndEnabled || !IsSeated || Time.unscaledTime < nextActionTime) return false;
            if (!FindClearExit(out Vector3 exitPosition))
            {
                Feedback = "EXIT BLOCKED  /  CLEAR THE SPACE";
                return false;
            }
            Feedback = null;
            State = SeatState.Leaving;
            transition = StartCoroutine(ChangeSeat(false, exitPosition));
            return true;
        }

        IEnumerator ChangeSeat(bool entering, Vector3 exitPosition)
        {
            yield return viewFade.FadeTo(1f, fadeSeconds);
            if (entering)
            {
                origin.MatchOriginUpCameraForward(Vector3.up, seatAnchor.forward);
                origin.MoveCameraToWorldLocation(seatAnchor.position + Vector3.up * seatedEyeHeight);
            }
            else MoveToExit(exitPosition);
            Physics.SyncTransforms();
            yield return new WaitForSecondsRealtime(blackHoldSeconds);
            yield return viewFade.FadeTo(0f, fadeSeconds);
            State = entering ? SeatState.Seated : SeatState.Standing;
            if (!entering) UnlockLocomotion();
            nextActionTime = Time.unscaledTime + .4f;
            transition = null;
            if (entering) onSeated.Invoke(); else onStanding.Invoke();
        }

        void LockLocomotion()
        {
            standingOriginY = origin.Origin.transform.position.y;
            for (int i = 0; i < providers.Length; i++)
            {
                providerStates[i] = providers[i].enabled;
                providers[i].enabled = false;
            }
            characterWasEnabled = character && character.enabled;
            if (character) character.enabled = false;
            locked = true;
        }

        void UnlockLocomotion()
        {
            if (!locked) return;
            if (character) character.enabled = characterWasEnabled;
            for (int i = 0; i < providers.Length; i++)
                if (providers[i]) providers[i].enabled = providerStates[i];
            locked = false;
        }

        void MoveToExit(Vector3 position)
        {
            // Restore floor height while keeping the user's current physical head height and orientation.
            position.y = origin.Camera.transform.position.y + standingOriginY - origin.Origin.transform.position.y;
            origin.MoveCameraToWorldLocation(position);
        }

        bool FindClearExit(out Vector3 position)
        {
            // Preferred position behind the chair; side alternatives if a future prop blocks it.
            Vector3[] offsets = { Vector3.zero, Vector3.left * .8f, Vector3.right * .8f };
            foreach (var offset in offsets)
            {
                position = exitAnchor.TransformPoint(offset);
                var overlaps = Physics.OverlapCapsule(position + Vector3.up * .32f,
                    position + Vector3.up * 1.55f, .23f, ~0, QueryTriggerInteraction.Ignore);
                bool clear = true;
                foreach (var collider in overlaps)
                    if (!collider.transform.IsChildOf(origin.transform)) { clear = false; break; }
                if (clear) return true;
            }
            position = exitAnchor.position;
            return false;
        }

        void OnDisable()
        {
            sitInput?.Disable(); leaveInput?.Disable();
            if (transition != null) StopCoroutine(transition);
            transition = null;
            if (locked && origin && exitAnchor)
            {
                if (FindClearExit(out Vector3 position)) MoveToExit(position);
                else origin.Origin.transform.position += Vector3.up * (standingOriginY - origin.Origin.transform.position.y);
            }
            if (viewFade) viewFade.SetAlpha(0);
            UnlockLocomotion();
            State = SeatState.Standing;
        }

        void OnDestroy() { sitInput?.Dispose(); leaveInput?.Dispose(); }

        void OnDrawGizmosSelected()
        {
            if (!seatAnchor) return;
            Gizmos.color = new Color(1f, .8f, .45f, .6f);
            Gizmos.DrawWireSphere(seatAnchor.position, approachDistance);
            Gizmos.DrawSphere(seatAnchor.position + Vector3.up * seatedEyeHeight, .06f);
            if (exitAnchor) Gizmos.DrawWireCube(exitAnchor.position + Vector3.up * .8f, new Vector3(.46f, 1.6f, .46f));
        }
    }
}
