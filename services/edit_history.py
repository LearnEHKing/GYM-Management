from models import EditHistory, db


def record_edit(owner_id, actor_id, actor_name, entity_type, entity_id, action, reason, before_data, after_data,
                context_id=None):
    db.session.add(EditHistory(
        owner_id=owner_id,
        actor_id=actor_id,
        actor_name=actor_name,
        entity_type=entity_type,
        entity_id=entity_id,
        context_id=context_id,
        action=action,
        reason=reason,
        before_data=before_data,
        after_data=after_data,
    ))