'use strict';

/**
 * SelfForwardRewrite plugin for ZoneMTA
 *
 * Problem: When someone@gmail.com sends to member@club.ch,
 * which forwards back to someone@gmail.com, Gmail silently drops
 * the message as a self-loop even though SRS envelope rewriting is correct.
 *
 * Solution: Before delivery, check if the SRS-decoded original sender
 * matches the delivery recipient. If so, rewrite the From: header to
 * the internal club address, breaking the self-loop detection.
 *
 * Runs in ZoneMTA sender process, after SRS rewriting has already occurred.
 */

module.exports.title = 'SelfForwardRewrite';

module.exports.init = (app, done) => {
    app.addHook('sender:headers', async (delivery, connection, next) => {
        // Only act on forwarded messages — not authenticated outbound
        if (delivery.interface !== 'forwarder') return next();

        const recipient = delivery.envelope.to || '';
        const envelopeFrom = delivery.envelope.from || '';

        if (!envelopeFrom || !recipient) return next();

        // Decode SRS to get the original sender
        // SRS0=xxxx=TT=gmail.com=user@club.ch → user@gmail.com
        let originalSender = envelopeFrom;
        const srsMatch = envelopeFrom.match(/SRS\d+=[^=]+=\w+=([^=]+)=([^@]+)@/i);
        if (srsMatch) {
            originalSender = `${srsMatch[2]}@${srsMatch[1]}`;
        }

        // If original sender matches delivery recipient → self-forward
        if (originalSender.toLowerCase() !== recipient.toLowerCase()) {
            return next();
        }

        // Look up the WildDuck user whose forwarding target matches the sender
        try {
            const user = await app.db.users
                .collection('users')
                .findOne(
                    { targets: { $elemMatch: { value: originalSender } } },
                    { projection: { address: 1, username: 1 } }
                );

            if (user && user.address && user.address !== originalSender) {
                delivery.headers.remove('From');
                delivery.headers.add('From', `<${user.address}>`, 0);

                app.logger.info(
                    'SelfForwardRewrite',
                    '%s Rewrote From: %s → %s (self-forward prevented)',
                    delivery.id, originalSender, user.address
                );
            }
        } catch (e) {
            app.logger.error(
                'SelfForwardRewrite',
                '%s Error looking up user: %s',
                delivery.id, e.message
            );
        }

        return next();
    });

    done();
};
